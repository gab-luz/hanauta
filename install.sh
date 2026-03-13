#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
VSCODE_EXTENSION_SRC="$SCRIPT_DIR/hanauta/vscode-wallpaper-theme"
VSCODE_EXTENSION_ID="hanauta.hanauta-wallpaper-theme"

INSTALL_EDITOR_EXTENSIONS_AUTO=false
INSTALL_VSCODE_ONLY=false
INSTALL_VSCODIUM_ONLY=false
INSTALL_NOTIFICATION_DAEMON_ONLY=false

RICH_AVAILABLE=false
if python3 -c "import rich" 2>/dev/null; then
  RICH_AVAILABLE=true
fi

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

info() { printf "${CYAN}[INFO]${NC} %s\n" "$*"; }
warn() { printf "${YELLOW}[WARN]${NC} %s\n" "$*"; }
error() { printf "${RED}[ERROR]${NC} %s\n" "$*"; }
success() { printf "${GREEN}[OK]${NC} %s\n" "$*"; }

detect_debian_like() {
  if [ -r /etc/os-release ]; then
    . /etc/os-release
    if [ "${ID:-}" = "debian" ] || [ "${ID_LIKE:-}" = "debian" ] || [ "${ID:-}" = "ubuntu" ]; then
      return 0
    fi
  fi
  return 1
}

detect_arch() {
  if [ -r /etc/os-release ]; then
    . /etc/os-release
    if [ "${ID:-}" = "arch" ] || [ "${ID_LIKE:-}" = "arch" ]; then
      return 0
    fi
  fi
  return 1
}

need_cmd() { command -v "$1" >/dev/null 2>&1; }

install_editor_extension_dir() {
  local target_root="$1"
  local label="$2"
  local target_dir="$target_root/$VSCODE_EXTENSION_ID"

  if [ ! -d "$VSCODE_EXTENSION_SRC" ]; then
    error "Extension source not found at $VSCODE_EXTENSION_SRC"
    return 1
  fi

  mkdir -p "$target_root"
  rm -rf "$target_dir"
  mkdir -p "$target_dir"
  cp -a "$VSCODE_EXTENSION_SRC/." "$target_dir/"
  success "$label extension installed to $target_dir"
}

install_vscode_extension() {
  install_editor_extension_dir "$HOME/.vscode/extensions" "VS Code"
}

install_vscodium_extension() {
  install_editor_extension_dir "$HOME/.vscode-oss/extensions" "VSCodium"
}

install_detected_editor_extensions() {
  local installed_any=false

  if need_cmd code || [ -d "$HOME/.vscode" ]; then
    install_vscode_extension
    installed_any=true
  fi

  if need_cmd codium || [ -d "$HOME/.vscode-oss" ]; then
    install_vscodium_extension
    installed_any=true
  fi

  if [ "$installed_any" = false ]; then
    info "No VS Code or VSCodium installation detected; skipping editor extension install"
  fi
}

parse_args() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --vscode)
        INSTALL_EDITOR_EXTENSIONS_AUTO=false
        INSTALL_VSCODE_ONLY=true
        ;;
      --vscodium)
        INSTALL_EDITOR_EXTENSIONS_AUTO=false
        INSTALL_VSCODIUM_ONLY=true
        ;;
      --notification-daemon)
        INSTALL_NOTIFICATION_DAEMON_ONLY=true
        ;;
      -h|--help)
        cat <<EOF
Usage: ./install.sh [--vscode] [--vscodium] [--notification-daemon]

Without flags:
  Runs the full desktop install only.

With flags:
  --vscode    Install only the VS Code extension
  --vscodium  Install only the VSCodium extension
  --notification-daemon  Install only the Hanauta notification daemon components
EOF
        exit 0
        ;;
      *)
        error "Unknown argument: $1"
        exit 1
        ;;
    esac
    shift
  done
}

print_banner() {
  echo -e "${MAGENTA}${BOLD}"
  cat << 'EOF'
♫  _                                _
  | |__   __ _ _ __   __ _ _   _| |_ __ _
  | '_ \ / _` | '_ \ / _` | | | | __/ _` |
  | | | | (_| | | | | (_| | |_| | || (_| |
  |_| |_|\__,_|_| |_|\__,_|\__,_|\__\__,_|

      Desktop Installer
EOF
  echo -e "${NC}"
  echo -e "${CYAN}Setting up your i3 desktop environment...${NC}"
  echo ""
}

install_rich() {
  if ! need_cmd uv; then
    info "Installing uv (fast Python package manager)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    need_cmd uv || { error "Failed to install uv"; return 1; }
  fi
  
  if ! python3 -c "import rich" 2>/dev/null; then
    info "Installing rich for colorful output..."
    pip install rich --quiet 2>/dev/null || pip3 install rich --quiet 2>/dev/null || true
  fi
}

setup_python_venv() {
  local venv_dir="$SCRIPT_DIR/.venv"
  
  if [ -d "$venv_dir" ]; then
    info "Python venv already exists"
    return 0
  fi
  
  if ! need_cmd uv; then
    error "uv not found. Cannot create Python environment."
    return 1
  fi
  
  info "Creating Python virtual environment..."
  uv venv "$venv_dir"
  
  info "Installing Python dependencies from pyproject.toml..."
  cd "$SCRIPT_DIR"
  uv sync
  
  success "Python environment ready"
}

apt_has_package() {
  apt-cache show "$1" >/dev/null 2>&1
}

pacman_has_package() {
  pacman -Si "$1" >/dev/null 2>&1
}

install_apt_group() {
  local label="$1"
  shift
  local -a available=()
  local -a missing=()

  for pkg in "$@"; do
    if apt_has_package "$pkg"; then
      available+=("$pkg")
    else
      missing+=("$pkg")
    fi
  done

  if [ ${#available[@]} -gt 0 ]; then
    info "Installing Debian packages ($label): ${available[*]}"
    sudo apt-get install -y "${available[@]}"
  fi

  if [ ${#missing[@]} -gt 0 ]; then
    warn "Skipping unavailable Debian packages ($label): ${missing[*]}"
  fi
}

install_pacman_group() {
  local label="$1"
  shift
  local -a available=()
  local -a missing=()

  for pkg in "$@"; do
    if pacman_has_package "$pkg"; then
      available+=("$pkg")
    else
      missing+=("$pkg")
    fi
  done

  if [ ${#available[@]} -gt 0 ]; then
    info "Installing Arch packages ($label): ${available[*]}"
    sudo pacman -S --needed --noconfirm "${available[@]}"
  fi

  if [ ${#missing[@]} -gt 0 ]; then
    warn "Skipping unavailable Arch packages ($label): ${missing[*]}"
  fi
}

install_packages_debian() {
  local -a core_pkgs=(
    i3-wm rofi feh picom
    x11-xserver-utils x11-utils xdotool xclip
    jq curl ffmpeg rsync
    flameshot scrot maim
    playerctl brightnessctl
    pulseaudio-utils pamixer
    network-manager wireless-tools
    i3lock
    xfce4-power-manager lxqt-policykit
    libnotify-bin
    kitty
    bluez
    cava
    python3 python3-pip python3-venv
    libxkbcommon-x11-0
    libxcb-cursor0
    sassc
    xdg-user-dirs
    libgtk-3-bin
  )
  local -a optional_pkgs=(
    copyq clipit plank ukui-window-switch
    kdeconnect qt6-tools-dev-tools policykit-1-gnome
  )

  echo -e "${CYAN}[*]${NC} Updating package lists..."
  sudo apt-get update -qq

  install_apt_group "core desktop stack" "${core_pkgs[@]}"
  install_apt_group "optional integrations" "${optional_pkgs[@]}"
  success "System packages installed"
}

install_packages_arch() {
  local -a core_pkgs=(
    i3-wm rofi feh picom
    xorg-xrandr xorg-xsetroot xorg-xwininfo xorg-xev xdotool xclip
    jq curl ffmpeg rsync
    flameshot scrot maim
    playerctl brightnessctl
    pulseaudio pamixer
    networkmanager wireless_tools
    i3lock
    xfce4-power-manager lxqt-policykit
    libnotify
    kitty
    bluez bluez-utils
    cava
    python python-pip
    libxkbcommon-x11
    libxcb-cursor
    sassc
    xdg-user-dirs
    gtk3
  )
  local -a optional_pkgs=(
    copyq clipit plank ukui-window-switch
    kdeconnect qt6-tools polkit-gnome
    pacman-contrib
  )

  install_pacman_group "core desktop stack" "${core_pkgs[@]}"
  install_pacman_group "optional integrations" "${optional_pkgs[@]}"
  success "System packages installed"
}

install_deadd_debian() {
  local target_dir="$HOME/.config/i3/bin"
  local target="$target_dir/deadd-notification-center"

  if [ -x "$target" ]; then
    info "deadd-notification-center already installed"
    return 0
  fi

  if ! need_cmd curl; then
    warn "curl not found; cannot download deadd-notification-center."
    return 1
  fi

  info "Installing deadd-notification-center..."
  mkdir -p "$target_dir"
  curl -fsSL \
    "https://github.com/phuhl/linux_notification_center/releases/download/2.1.1/deadd-notification-center" \
    -o "$target"
  chmod +x "$target"
  success "deadd-notification-center installed"
}

install_deadd_arch() {
  if need_cmd deadd-notification-center; then
    info "deadd-notification-center already installed"
    return 0
  fi

  if need_cmd yay; then
    info "Installing deadd-notification-center via AUR..."
    yay -S --noconfirm deadd-notification-center
  elif need_cmd paru; then
    info "Installing deadd-notification-center via AUR..."
    paru -S --noconfirm deadd-notification-center
  else
    warn "yay/paru not found; install deadd-notification-center from AUR manually."
  fi
}

install_notification_packages_debian() {
  local -a pkgs=(
    python3 python3-pip python3-venv
    libnotify-bin jq curl
    x11-utils x11-xserver-utils
  )

  echo -e "${CYAN}[*]${NC} Updating package lists..."
  sudo apt-get update -qq
  install_apt_group "notification daemon" "${pkgs[@]}"
}

install_notification_packages_arch() {
  local -a pkgs=(
    python python-pip
    libnotify jq curl
    xorg-xrandr xorg-xsetroot
  )
  install_pacman_group "notification daemon" "${pkgs[@]}"
}

copy_dotfiles() {
  local target="$HOME/.config/i3"
  if [ -d "$target" ] && [ ! -L "$target" ]; then
    local backup="$HOME/.config/i3.backup-$(date +%Y%m%d-%H%M%S)"
    info "Backing up existing i3 config to $backup"
    mkdir -p "$backup"
    rsync -a "$target/" "$backup/"
  fi

  info "Copying dotfiles..."
  mkdir -p "$target"
  rsync -a \
    --exclude '.git' \
    --exclude 'backups' \
    --exclude 'install.sh' \
    "$SCRIPT_DIR/" \
    "$target/"
  success "Dotfiles copied"
}

ensure_dock_defaults() {
  local src="$SCRIPT_DIR/hanauta/src/pyqt/dock/dock.toml"
  local dst="$HOME/.config/i3/hanauta/src/pyqt/dock/dock.toml"

  if [ ! -f "$src" ]; then
    warn "Dock config template not found at $src"
    return 1
  fi

  mkdir -p "$(dirname "$dst")"
  if [ ! -f "$dst" ]; then
    cp "$src" "$dst"
  fi

  if rg -q 'window_name = \[' "$dst" 2>/dev/null; then
    success "Dock blacklist defaults are installed"
  else
    warn "Dock config is present but blacklist defaults could not be verified"
  fi
}

link_configs() {
  mkdir -p "$HOME/.config/sxhkd" "$HOME/.config/picom" "$HOME/.config/dunst"

  ln -sfn "$HOME/.config/i3/sxhkdrc" "$HOME/.config/sxhkd/sxhkdrc"
  ln -sfn "$HOME/.config/i3/picom.conf" "$HOME/.config/picom/picom.conf"
  ln -sfn "$HOME/.config/i3/dunstrc" "$HOME/.config/dunst/dunstrc" 2>/dev/null || true
  success "Config symlinks created"
}

make_exec() {
  local root="$HOME/.config/i3"
  chmod +x "$root/bspwmrc" 2>/dev/null || true
  chmod +x "$root/scripts/start-eww-ui" 2>/dev/null || true
  chmod +x "$root/scripts/openapps" 2>/dev/null || true
  chmod +x "$root/scripts/fix-plank" 2>/dev/null || true
  chmod +x "$root/scripts/floating" 2>/dev/null || true

  while IFS= read -r -d '' f; do
    if head -c 2 "$f" 2>/dev/null | grep -q '^#!'; then
      chmod +x "$f" 2>/dev/null || true
    fi
  done < <(find "$root/scripts" "$root/hanauta/src/eww/scripts" -type f -print0 2>/dev/null)

  if [ -d "$root/bin" ]; then
    find "$root/bin" -maxdepth 1 -type f -exec chmod +x {} \; 2>/dev/null || true
  fi
  
  success "Scripts made executable"
}

install_local_binaries() {
  local root="$HOME/.config/i3"
  local src_dir="$root/bin"
  local target_dir="$HOME/.local/bin"
  local -a linked=()

  mkdir -p "$target_dir"
  if [ ! -d "$src_dir" ]; then
    warn "No bundled binaries found in $src_dir"
    return 0
  fi

  for name in matugen hellwal i3lock-color dunstctl dunstify; do
    if [ -x "$src_dir/$name" ]; then
      ln -sfn "$src_dir/$name" "$target_dir/$name"
      linked+=("$name")
    fi
  done

  if [ ${#linked[@]} -gt 0 ]; then
    success "Bundled binaries linked into $target_dir: ${linked[*]}"
  else
    warn "No bundled public binaries were linked"
  fi
}

print_summary() {
  echo ""
  echo -e "${GREEN}${BOLD}========================================${NC}"
  echo -e "${GREEN}${BOLD}  Installation Complete!${NC}"
  echo -e "${GREEN}${BOLD}========================================${NC}"
  echo ""
  echo -e "${CYAN}Summary:${NC}"
  echo -e "  ${GREEN}✓${NC} System packages"
  echo -e "  ${GREEN}✓${NC} Python environment (uv)"
  echo -e "  ${GREEN}✓${NC} Dotfiles"
  echo -e "  ${GREEN}✓${NC} Config links"
  echo -e "  ${GREEN}✓${NC} Bundled binaries"
  echo ""
}

post_notes() {
  echo ""
  echo -e "${YELLOW}Important notes:${NC}"
  echo -e "  • Ensure ${BOLD}~/.local/bin${NC} is on PATH so bundled binaries like ${BOLD}matugen${NC} and ${BOLD}hellwal${NC} are usable"
  echo -e "  • Optional integrations such as ${BOLD}ukui-window-switch${NC}, ${BOLD}clipit/copyq${NC}, and ${BOLD}KDE Connect${NC} may be skipped if unavailable in your distro repositories"
  echo -e "  • PyQt6 notification center opens from the bar"
  echo ""
  echo -e "${CYAN}Next steps:${NC}"
  echo -e "  1. Log out and log back in, or reload i3"
  echo -e "  2. Verify ${BOLD}matugen --help${NC} and ${BOLD}hellwal --help${NC} work from your shell"
  echo ""
}

main() {
  parse_args "$@"

  if [ "$INSTALL_VSCODE_ONLY" = true ] || [ "$INSTALL_VSCODIUM_ONLY" = true ]; then
    if [ "$INSTALL_VSCODE_ONLY" = true ]; then
      install_vscode_extension
    fi
    if [ "$INSTALL_VSCODIUM_ONLY" = true ]; then
      install_vscodium_extension
    fi
    info "Done!"
    return 0
  fi

  print_banner

  if ! need_cmd sudo; then
    warn "sudo not found; package install may fail unless run as root."
  fi

  install_rich

  if detect_debian_like; then
    info "Detected Debian-based distribution"
    if [ "$INSTALL_NOTIFICATION_DAEMON_ONLY" = true ]; then
      install_notification_packages_debian
    else
      install_packages_debian
    fi
  elif detect_arch; then
    info "Detected Arch Linux distribution"
    if [ "$INSTALL_NOTIFICATION_DAEMON_ONLY" = true ]; then
      install_notification_packages_arch
    else
      install_packages_arch
    fi
  else
    warn "Unknown distro; skipping system package install."
  fi

  setup_python_venv
  copy_dotfiles
  ensure_dock_defaults
  link_configs
  make_exec
  install_local_binaries
  if [ "$INSTALL_NOTIFICATION_DAEMON_ONLY" = false ] && [ "$INSTALL_EDITOR_EXTENSIONS_AUTO" = true ]; then
    install_detected_editor_extensions
  fi

  print_summary
  post_notes

  info "Done!"
}

main "$@"
