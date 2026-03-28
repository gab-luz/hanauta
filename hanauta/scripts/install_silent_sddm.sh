#!/usr/bin/env bash
set -euo pipefail

THEME_REPO_URL="https://github.com/uiriansan/SilentSDDM"
THEME_REPO_BRANCH="main"
THEME_DEST="/usr/share/sddm/themes/silent"
SDDM_CONF="/etc/sddm.conf"

COLOR_RED='\033[0;31m'
COLOR_GREEN='\033[0;32m'
COLOR_YELLOW='\033[1;33m'
COLOR_CYAN='\033[0;36m'
COLOR_RESET='\033[0m'

info() { printf "${COLOR_CYAN}[INFO]${COLOR_RESET} %s\n" "$*"; }
warn() { printf "${COLOR_YELLOW}[WARN]${COLOR_RESET} %s\n" "$*"; }
error() { printf "${COLOR_RED}[ERROR]${COLOR_RESET} %s\n" "$*" >&2; }
success() { printf "${COLOR_GREEN}[OK]${COLOR_RESET} %s\n" "$*"; }

need_cmd() { command -v "$1" >/dev/null 2>&1; }

if [ "${EUID:-$(id -u)}" -ne 0 ]; then
  if need_cmd sudo; then
    exec sudo "$0" "$@"
  fi
  error "This script needs root privileges (sudo/root)."
  exit 1
fi

detect_distro() {
  if [ -r /etc/os-release ]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    case "${ID:-}" in
      debian|ubuntu) printf '%s\n' "debian"; return 0 ;;
      arch) printf '%s\n' "arch"; return 0 ;;
    esac
    case "${ID_LIKE:-}" in
      *debian*) printf '%s\n' "debian"; return 0 ;;
      *arch*) printf '%s\n' "arch"; return 0 ;;
    esac
  fi
  printf '%s\n' "unknown"
}

apt_has_package() {
  apt-cache show "$1" >/dev/null 2>&1
}

pick_first_available_apt_package() {
  local pkg=""
  for pkg in "$@"; do
    if apt_has_package "$pkg"; then
      printf '%s\n' "$pkg"
      return 0
    fi
  done
  return 1
}

install_apt_if_available() {
  local label="$1"
  shift
  local -a pkgs=("$@")
  local -a available=()
  local p=""

  for p in "${pkgs[@]}"; do
    if apt_has_package "$p"; then
      available+=("$p")
    else
      warn "Skipping unavailable Debian package (${label}): ${p}"
    fi
  done

  if [ ${#available[@]} -gt 0 ]; then
    info "Installing Debian packages (${label}): ${available[*]}"
    apt-get install -y "${available[@]}"
  fi
}

install_dependencies_debian() {
  local svg_pkg=""
  local vkb_pkg=""
  local mm_pkg=""

  info "Updating apt metadata..."
  apt-get update -qq

  install_apt_if_available "base" sddm git rsync

  svg_pkg="$(pick_first_available_apt_package libqt6svg6 qml6-module-qtquick-controls qt6-svg-dev || true)"
  vkb_pkg="$(pick_first_available_apt_package qml6-module-qtquick-virtualkeyboard qt6-virtualkeyboard-dev || true)"
  mm_pkg="$(pick_first_available_apt_package qml6-module-qtmultimedia qt6-multimedia-dev || true)"

  [ -n "$svg_pkg" ] && install_apt_if_available "qt6 svg" "$svg_pkg" || warn "Could not resolve a Qt6 SVG runtime package on Debian."
  [ -n "$vkb_pkg" ] && install_apt_if_available "qt6 virtual keyboard" "$vkb_pkg" || warn "Could not resolve a Qt6 virtual keyboard package on Debian."
  [ -n "$mm_pkg" ] && install_apt_if_available "qt6 multimedia" "$mm_pkg" || warn "Could not resolve a Qt6 multimedia package on Debian."
}

install_dependencies_arch() {
  if ! need_cmd pacman; then
    error "pacman not found on Arch path"
    return 1
  fi
  info "Installing Arch packages for SilentSDDM..."
  pacman -S --needed --noconfirm sddm git rsync qt6-svg qt6-virtualkeyboard qt6-multimedia-ffmpeg
}

parse_version_digits() {
  local raw="$1"
  local cleaned=""
  cleaned="$(printf '%s' "$raw" | grep -Eo '[0-9]+(\.[0-9]+){1,2}' | head -n 1 || true)"
  if [ -z "$cleaned" ]; then
    return 1
  fi
  printf '%s\n' "$cleaned"
}

version_at_least_0_21() {
  local v="$1"
  local major="0"
  local minor="0"

  major="${v%%.*}"
  minor="$(printf '%s' "$v" | cut -d. -f2)"
  minor="${minor:-0}"

  if [ "$major" -gt 0 ]; then
    return 0
  fi
  [ "$minor" -ge 21 ]
}

detect_sddm_version() {
  local distro="$1"
  local v=""

  if need_cmd sddm; then
    v="$(sddm --version 2>/dev/null | head -n 1 || true)"
    v="$(parse_version_digits "$v" || true)"
    if [ -n "$v" ]; then
      printf '%s\n' "$v"
      return 0
    fi
  fi

  if [ "$distro" = "debian" ] && need_cmd dpkg-query; then
    v="$(dpkg-query -W -f='${Version}' sddm 2>/dev/null || true)"
    v="$(parse_version_digits "$v" || true)"
    if [ -n "$v" ]; then
      printf '%s\n' "$v"
      return 0
    fi
  fi

  if [ "$distro" = "arch" ] && need_cmd pacman; then
    v="$(pacman -Q sddm 2>/dev/null | awk '{print $2}' || true)"
    v="$(parse_version_digits "$v" || true)"
    if [ -n "$v" ]; then
      printf '%s\n' "$v"
      return 0
    fi
  fi

  return 1
}

set_ini_key() {
  local file_path="$1"
  local section="$2"
  local key="$3"
  local value="$4"
  local temp_file=""

  temp_file="$(mktemp)"
  awk -v section="$section" -v key="$key" -v value="$value" '
    BEGIN {
      in_section = 0
      section_found = 0
      key_written = 0
    }
    function print_key() { print key "=" value }
    /^\[.*\]$/ {
      if (in_section && !key_written) { print_key(); key_written = 1 }
      if ($0 == "[" section "]") {
        in_section = 1
        section_found = 1
        key_written = 0
      } else {
        in_section = 0
      }
      print
      next
    }
    {
      if (in_section && $0 ~ "^[[:space:]]*" key "[[:space:]]*=") {
        if (!key_written) { print_key(); key_written = 1 }
        next
      }
      print
    }
    END {
      if (!section_found) {
        print ""
        print "[" section "]"
        print_key()
      } else if (in_section && !key_written) {
        print_key()
      }
    }
  ' "$file_path" > "$temp_file"

  cat "$temp_file" > "$file_path"
  rm -f "$temp_file"
}

configure_sddm() {
  local tmp_conf=""
  local backup=""

  tmp_conf="$(mktemp)"
  if [ -f "$SDDM_CONF" ]; then
    cp "$SDDM_CONF" "$tmp_conf"
    backup="${SDDM_CONF}.backup-$(date +%Y%m%d-%H%M%S)"
    cp "$SDDM_CONF" "$backup"
    success "Backed up SDDM config to $backup"
  else
    : > "$tmp_conf"
  fi

  set_ini_key "$tmp_conf" "Theme" "Current" "silent"
  set_ini_key "$tmp_conf" "General" "InputMethod" "qtvirtualkeyboard"
  set_ini_key "$tmp_conf" "General" "GreeterEnvironment" "QML2_IMPORT_PATH=/usr/share/sddm/themes/silent/components/,QT_IM_MODULE=qtvirtualkeyboard"

  cp "$tmp_conf" "$SDDM_CONF"
  rm -f "$tmp_conf"
  success "Configured $SDDM_CONF for SilentSDDM"
}

install_theme_files() {
  local tmp_root=""
  local repo_root=""

  if ! need_cmd git; then
    error "git is required"
    return 1
  fi
  if ! need_cmd rsync; then
    error "rsync is required"
    return 1
  fi

  tmp_root="$(mktemp -d)"
  repo_root="$tmp_root/SilentSDDM"

  info "Cloning SilentSDDM..."
  git clone --depth 1 --branch "$THEME_REPO_BRANCH" "$THEME_REPO_URL" "$repo_root" >/dev/null 2>&1

  info "Installing theme to $THEME_DEST"
  mkdir -p "$THEME_DEST"
  rsync -a --delete --exclude '.git' "$repo_root/" "$THEME_DEST/"

  if [ -d "$THEME_DEST/fonts" ]; then
    info "Installing SilentSDDM fonts to /usr/share/fonts"
    mkdir -p /usr/share/fonts
    rsync -a "$THEME_DEST/fonts/" /usr/share/fonts/
    need_cmd fc-cache && fc-cache -f /usr/share/fonts >/dev/null 2>&1 || true
  fi

  rm -rf "$tmp_root"
  success "SilentSDDM theme files installed"
}

enable_sddm_prompt() {
  local reply=""
  read -r -p "Enable sddm.service at boot now? [Y/n] " reply
  case "${reply,,}" in
    n|no)
      info "Skipped enabling sddm.service"
      ;;
    *)
      systemctl enable sddm.service
      success "Enabled sddm.service"
      ;;
  esac

  read -r -p "Restart sddm.service now? This can interrupt current session [y/N] " reply
  case "${reply,,}" in
    y|yes)
      systemctl restart sddm.service
      success "Restarted sddm.service"
      ;;
    *)
      info "Skipped restarting sddm.service"
      ;;
  esac
}

main() {
  local distro=""
  local version=""

  distro="$(detect_distro)"
  case "$distro" in
    debian)
      info "Detected Debian-like distro"
      install_dependencies_debian
      ;;
    arch)
      info "Detected Arch distro"
      install_dependencies_arch
      ;;
    *)
      warn "Unknown distro. Skipping dependency installation."
      ;;
  esac

  if version="$(detect_sddm_version "$distro")"; then
    if version_at_least_0_21 "$version"; then
      success "Detected SDDM version $version (>= 0.21.0)"
    else
      warn "Detected SDDM version $version (< 0.21.0). SilentSDDM may fail."
    fi
  else
    warn "Could not detect SDDM version from command/package metadata."
  fi

  install_theme_files
  configure_sddm

  if need_cmd systemctl; then
    enable_sddm_prompt
  else
    warn "systemctl not found; skipping service enable/restart."
  fi

  success "Done. Test theme from: $THEME_DEST"
  printf '  %s\n' "cd $THEME_DEST && ./test.sh"
}

main "$@"
