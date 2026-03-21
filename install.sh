#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
VSCODE_EXTENSION_SRC="$SCRIPT_DIR/hanauta/vscode-wallpaper-theme"
VSCODE_EXTENSION_ID="hanauta.hanauta-wallpaper-theme"

INSTALL_EDITOR_EXTENSIONS_AUTO=false
INSTALL_VSCODE_ONLY=false
INSTALL_VSCODIUM_ONLY=false
INSTALL_NOTIFICATION_DAEMON_ONLY=false
INSTALL_QUICKSHELL_ONLY=false
INSTALL_WIREGUARD_SYSTEMD_ONLY=false
INSTALL_CUSTOM_THEMES=false
CUSTOM_THEMES_SELECTION=""
INSTALL_CUSTOM_THEMES_TO_SYSTEM=true

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

normalize_custom_theme_selection() {
  local raw="${1:-all}"
  raw="$(printf '%s' "$raw" | tr '[:upper:]' '[:lower:]')"
  case "$raw" in
    all|retrowave|dracula)
      printf '%s\n' "$raw"
      ;;
    *)
      return 1
      ;;
  esac
}

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
      --quickshell)
        INSTALL_QUICKSHELL_ONLY=true
        ;;
      --wireguard-systemd)
        INSTALL_WIREGUARD_SYSTEMD_ONLY=true
        ;;
      --custom-themes)
        INSTALL_CUSTOM_THEMES=true
        CUSTOM_THEMES_SELECTION="all"
        INSTALL_CUSTOM_THEMES_TO_SYSTEM=true
        ;;
      --custom-themes=*)
        INSTALL_CUSTOM_THEMES=true
        CUSTOM_THEMES_SELECTION="${1#*=}"
        INSTALL_CUSTOM_THEMES_TO_SYSTEM=true
        ;;
      --custom-themes-system)
        INSTALL_CUSTOM_THEMES=true
        INSTALL_CUSTOM_THEMES_TO_SYSTEM=true
        if [ -z "$CUSTOM_THEMES_SELECTION" ]; then
          CUSTOM_THEMES_SELECTION="all"
        fi
        ;;
      -h|--help)
        cat <<EOF
Usage: ./install.sh [--vscode] [--vscodium] [--notification-daemon] [--quickshell] [--wireguard-systemd] [--custom-themes[=retrowave|dracula|all]] [--custom-themes-system]

Without flags:
  Runs the full desktop install only.

With flags:
  --vscode    Install only the VS Code extension
  --vscodium  Install only the VSCodium extension
  --notification-daemon  Install only the Hanauta notification daemon components
  --quickshell  Install only the Quickshell runtime dependencies
  --wireguard-systemd  Offer a systemd-based WireGuard auto-start setup
  --custom-themes[=name]  Install vendored custom themes to both ~/.themes and /usr/share/themes by default. Accepted values: retrowave, dracula, all
  --custom-themes-system  Explicitly force system installation too (default for custom-theme installs)
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

confirm_yes() {
  local prompt="$1"
  local reply=""
  read -r -p "$prompt [y/N] " reply
  case "${reply,,}" in
    y|yes) return 0 ;;
    *) return 1 ;;
  esac
}

confirm_default_yes() {
  local prompt="$1"
  local reply=""
  read -r -p "$prompt [Y/n] " reply
  case "${reply,,}" in
    n|no) return 1 ;;
    *) return 0 ;;
  esac
}

install_wireguard_systemd_support_debian() {
  install_apt_group "wireguard systemd support" wireguard-tools
}

install_wireguard_systemd_support_arch() {
  install_pacman_group "wireguard systemd support" wireguard-tools
}

setup_wireguard_systemd() {
  local iface="${1:-}"
  if [ -z "$iface" ]; then
    error "WireGuard interface name is required."
    return 1
  fi

  if ! need_cmd sudo; then
    error "sudo is required for the systemd-based WireGuard setup."
    return 1
  fi

  if detect_debian_like; then
    install_wireguard_systemd_support_debian
  elif detect_arch; then
    install_wireguard_systemd_support_arch
  else
    warn "Unknown distro. Skipping package install and trying the existing systemd unit."
  fi

  if [ ! -f "/etc/wireguard/${iface}.conf" ]; then
    error "Expected /etc/wireguard/${iface}.conf but it was not found."
    return 1
  fi

  info "Enabling the systemd WireGuard unit for ${iface}..."
  sudo systemctl enable "wg-quick@${iface}.service"
  success "wg-quick@${iface}.service is enabled."

  if confirm_yes "Start ${iface} now as well?"; then
    sudo systemctl restart "wg-quick@${iface}.service"
    success "${iface} started through systemd."
  else
    info "Skipped starting ${iface} right now."
  fi
}

offer_wireguard_systemd_setup() {
  echo ""
  echo -e "${MAGENTA}${BOLD}Optional WireGuard Setup${NC}"
  echo -e "Enable a ${BOLD}systemd-based WireGuard auto-start${NC} for one interface."
  echo -e "This uses ${BOLD}sudo${NC}, enables ${BOLD}wg-quick@interface.service${NC}, and can reconnect the tunnel outside the i3 session."
  echo ""

  if ! confirm_yes "Do you want to continue with the systemd-based WireGuard setup?"; then
    info "Skipping systemd-based WireGuard setup."
    return 0
  fi

  warn "This will make WireGuard managed by systemd at startup, not just by the desktop session."
  if ! confirm_yes "Are you absolutely sure you want to enable this system-level WireGuard setup?"; then
    info "Second confirmation declined. Skipping systemd-based WireGuard setup."
    return 0
  fi

  local iface=""
  read -r -p "Enter the WireGuard interface name to enable at startup (example: wg0): " iface
  iface="${iface// /}"
  if [ -z "$iface" ]; then
    warn "No interface entered. Skipping systemd-based WireGuard setup."
    return 0
  fi

  setup_wireguard_systemd "$iface"
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
    python3-pyqt6.qtwebengine
    build-essential pkg-config
    libglib2.0-dev libgtk-3-dev
    qt6-base-dev
    qt6-declarative-dev
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
    python-pyqt6-webengine
    gcc pkgconf glib2
    qt6-base
    qt6-declarative
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

install_quickshell_packages_debian() {
  local -a pkgs=(
    quickshell
  )

  echo -e "${CYAN}[*]${NC} Updating package lists..."
  sudo apt-get update -qq
  warn "Quickshell is Wayland-oriented and not part of the default Hanauta X11 base install."
  install_apt_group "quickshell" "${pkgs[@]}"
}

install_quickshell_packages_arch() {
  if pacman_has_package quickshell; then
    install_pacman_group "quickshell" quickshell
    return 0
  fi

  if need_cmd yay; then
    info "Installing quickshell via AUR..."
    yay -S --noconfirm quickshell
  elif need_cmd paru; then
    info "Installing quickshell via AUR..."
    paru -S --noconfirm quickshell
  else
    warn "quickshell not found in pacman repos and yay/paru is unavailable."
    warn "Install quickshell manually, then rerun the calendar popup."
  fi
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
    build-essential pkg-config
    libglib2.0-dev libgtk-3-dev
    qt6-base-dev
    qt6-declarative-dev
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
    gcc pkgconf glib2 gtk3
    qt6-base
    qt6-declarative
    libnotify jq curl
    xorg-xrandr xorg-xsetroot
  )
  install_pacman_group "notification daemon" "${pkgs[@]}"
}

build_native_services() {
  local root="$HOME/.config/i3"
  local build_script="$root/hanauta/src/service/build.sh"

  if [ ! -f "$build_script" ]; then
    warn "Native service build script not found at $build_script"
    return 1
  fi

  info "Building native Hanauta C services..."
  if (cd "$root" && bash "$build_script"); then
    success "Native Hanauta services built"
    return 0
  fi

  error "Failed to build native Hanauta services"
  return 1
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
  mkdir -p "$HOME/.config/sxhkd" "$HOME/.config/picom"

  ln -sfn "$HOME/.config/i3/sxhkdrc" "$HOME/.config/sxhkd/sxhkdrc"
  ln -sfn "$HOME/.config/i3/picom.conf" "$HOME/.config/picom/picom.conf"
  success "Config symlinks created"
}

make_exec() {
  local root="$HOME/.config/i3"
  chmod +x "$root/bspwmrc" 2>/dev/null || true
  chmod +x "$root/scripts/openapps" 2>/dev/null || true
  chmod +x "$root/scripts/fix-plank" 2>/dev/null || true
  chmod +x "$root/scripts/floating" 2>/dev/null || true

  while IFS= read -r -d '' f; do
    if head -c 2 "$f" 2>/dev/null | grep -q '^#!'; then
      chmod +x "$f" 2>/dev/null || true
    fi
  done < <(find "$root/scripts" "$root/hanauta/scripts" -type f -print0 2>/dev/null)

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

  for name in matugen hellwal i3lock-color hanauta-notifyctl hanauta-notify-send hanauta-clock; do
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

ensure_hanauta_settings() {
  local settings_script="$HOME/.config/i3/hanauta/src/pyqt/settings-page/settings.py"
  local state_dir="$HOME/.local/state/hanauta/notification-center"
  local settings_file="$state_dir/settings.json"
  local backup_file=""
  local had_existing=false

  if [ ! -f "$settings_script" ]; then
    warn "Settings script not found at $settings_script; skipping settings migration"
    return 0
  fi

  mkdir -p "$state_dir"

  if [ -f "$settings_file" ]; then
    had_existing=true
    backup_file="$state_dir/settings.backup-$(date +%Y%m%d-%H%M%S).json"
    cp "$settings_file" "$backup_file"
    info "Backed up existing Hanauta settings to $backup_file"
  else
    info "Creating initial Hanauta settings file with bundled defaults"
  fi

  if python3 "$settings_script" --ensure-settings; then
    if [ "$had_existing" = true ]; then
      success "Hanauta settings preserved and merged with any new defaults"
    else
      success "Hanauta settings created"
    fi
  else
    error "Failed to prepare Hanauta settings"
    return 1
  fi
}

copy_theme_tree() {
  local source_dir="$1"
  local target_dir="$2"
  mkdir -p "$(dirname "$target_dir")"
  rm -rf "$target_dir"
  mkdir -p "$target_dir"
  rsync -a \
    --exclude '.git' \
    --exclude '.github' \
    --exclude 'node_modules' \
    "$source_dir/" \
    "$target_dir/"
}

install_retrowave_theme_to() {
  local destination_root="$1"
  local source_root="$SCRIPT_DIR/hanauta/vendor/themes/retrowave-theme/src/retrowave"
  local target_root="$destination_root/Retrowave"

  if [ ! -d "$source_root" ]; then
    warn "Retrowave source not found at $source_root"
    return 1
  fi
  if ! need_cmd sassc; then
    warn "sassc is required to build the Retrowave GTK theme."
    return 1
  fi

  rm -rf "$target_root"
  mkdir -p "$target_root/gtk-3.0" "$target_root/gtk-4.0"
  cp "$source_root/index.theme" "$target_root/index.theme"
  if [ -d "$source_root/gtk-2.0" ]; then
    copy_theme_tree "$source_root/gtk-2.0" "$target_root/gtk-2.0"
  fi
  if [ -d "$source_root/gtk-3.0/assets" ]; then
    copy_theme_tree "$source_root/gtk-3.0/assets" "$target_root/gtk-3.0/assets"
  fi
  sassc -I "$source_root/gtk-3.0" "$source_root/gtk-3.0/gtk.scss" "$target_root/gtk-3.0/gtk.css"
  cp "$target_root/gtk-3.0/gtk.css" "$target_root/gtk-4.0/gtk.css"
  success "Retrowave installed to $target_root"
}

install_dracula_theme_to() {
  local destination_root="$1"
  local source_root="$SCRIPT_DIR/hanauta/vendor/themes/dracula-gtk"
  local target_root="$destination_root/Dracula"

  if [ ! -d "$source_root" ]; then
    warn "Dracula source not found at $source_root"
    return 1
  fi

  copy_theme_tree "$source_root" "$target_root"
  success "Dracula installed to $target_root"
}

install_selected_theme_to_root() {
  local theme_key="$1"
  local destination_root="$2"
  case "$theme_key" in
    retrowave) install_retrowave_theme_to "$destination_root" ;;
    dracula) install_dracula_theme_to "$destination_root" ;;
    *) warn "Unknown custom theme: $theme_key"; return 1 ;;
  esac
}

install_custom_themes_for_root() {
  local selection="$1"
  local destination_root="$2"
  local -a themes=()
  case "$selection" in
    all) themes=(retrowave dracula) ;;
    retrowave|dracula) themes=("$selection") ;;
    *)
      error "Unsupported custom theme selection: $selection"
      return 1
      ;;
  esac

  mkdir -p "$destination_root"
  for theme in "${themes[@]}"; do
    install_selected_theme_to_root "$theme" "$destination_root"
  done
}

install_custom_themes_system() {
  local selection="$1"
  if ! need_cmd sudo; then
    warn "sudo not found; skipping installation to /usr/share/themes"
    return 0
  fi
  local temp_root
  temp_root="$(mktemp -d)"
  install_custom_themes_for_root "$selection" "$temp_root"
  info "Copying selected custom themes into /usr/share/themes with sudo..."
  sudo mkdir -p /usr/share/themes
  for theme_dir in "$temp_root"/*; do
    [ -d "$theme_dir" ] || continue
    sudo rm -rf "/usr/share/themes/$(basename "$theme_dir")"
    sudo cp -a "$theme_dir" "/usr/share/themes/"
  done
  rm -rf "$temp_root"
  success "Selected custom themes installed system-wide"
}

offer_custom_theme_install() {
  local selection="${CUSTOM_THEMES_SELECTION:-}"
  local reply=""

  if [ -n "$selection" ]; then
    selection="$(normalize_custom_theme_selection "$selection")" || {
      error "Invalid custom theme selection: $selection"
      return 1
    }
  else
    echo ""
    echo -e "${MAGENTA}${BOLD}Optional Custom Themes${NC}"
    echo -e "Install Hanauta's vendored GTK themes: ${BOLD}Retrowave${NC}, ${BOLD}Dracula${NC}, or ${BOLD}both${NC}."
    if ! confirm_yes "Do you want to install custom themes for Hanauta?"; then
      info "Skipping custom theme installation."
      return 0
    fi
    echo "Choose which custom themes to install:"
    echo "  1. All custom themes"
    echo "  2. Retrowave only"
    echo "  3. Dracula only"
    read -r -p "Selection [1-3]: " reply
    case "${reply:-1}" in
      1|"") selection="all" ;;
      2) selection="retrowave" ;;
      3) selection="dracula" ;;
      *) warn "Unknown selection. Installing all custom themes."; selection="all" ;;
    esac
    if ! confirm_default_yes "Also install the selected custom themes into /usr/share/themes using sudo for apps like Thunar?"; then
      INSTALL_CUSTOM_THEMES_TO_SYSTEM=false
    fi
  fi

  info "Installing custom themes to $HOME/.themes..."
  install_custom_themes_for_root "$selection" "$HOME/.themes"
  if [ "$INSTALL_CUSTOM_THEMES_TO_SYSTEM" = true ]; then
    install_custom_themes_system "$selection"
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
  echo -e "  ${GREEN}✓${NC} Optional custom themes"
  echo ""
}

post_notes() {
  echo ""
  echo -e "${YELLOW}Important notes:${NC}"
  echo -e "  • Ensure ${BOLD}~/.local/bin${NC} is on PATH so bundled binaries like ${BOLD}matugen${NC} and ${BOLD}hellwal${NC} are usable"
  echo -e "  • GTK themes are written for both ${BOLD}gtk-3.0${NC} and ${BOLD}gtk-4.0${NC} when applied from Hanauta Settings"
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

  if [ "$INSTALL_CUSTOM_THEMES" = true ]; then
    selection="${CUSTOM_THEMES_SELECTION:-all}"
    selection="$(normalize_custom_theme_selection "$selection")" || {
      error "Invalid custom theme selection: ${CUSTOM_THEMES_SELECTION:-}"
      return 1
    }
    CUSTOM_THEMES_SELECTION="$selection"
    print_banner
    offer_custom_theme_install
    info "Done!"
    return 0
  fi

  if [ "$INSTALL_WIREGUARD_SYSTEMD_ONLY" = true ]; then
    print_banner
    offer_wireguard_systemd_setup
    info "Done!"
    return 0
  fi

  if [ "$INSTALL_NOTIFICATION_DAEMON_ONLY" = true ] && [ "$INSTALL_QUICKSHELL_ONLY" = true ]; then
    error "Use only one of --notification-daemon or --quickshell."
    return 1
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
    elif [ "$INSTALL_QUICKSHELL_ONLY" = true ]; then
      install_quickshell_packages_debian
    else
      install_packages_debian
    fi
  elif detect_arch; then
    info "Detected Arch Linux distribution"
    if [ "$INSTALL_NOTIFICATION_DAEMON_ONLY" = true ]; then
      install_notification_packages_arch
    elif [ "$INSTALL_QUICKSHELL_ONLY" = true ]; then
      install_quickshell_packages_arch
    else
      install_packages_arch
    fi
  else
    warn "Unknown distro; skipping system package install."
  fi

  if [ "$INSTALL_QUICKSHELL_ONLY" = true ]; then
    info "Done!"
    return 0
  fi

  setup_python_venv
  copy_dotfiles
  build_native_services
  ensure_dock_defaults
  ensure_hanauta_settings
  link_configs
  make_exec
  install_local_binaries
  if [ "$INSTALL_NOTIFICATION_DAEMON_ONLY" = false ] && [ "$INSTALL_QUICKSHELL_ONLY" = false ] && [ "$INSTALL_EDITOR_EXTENSIONS_AUTO" = true ]; then
    install_detected_editor_extensions
  fi
  if [ "$INSTALL_NOTIFICATION_DAEMON_ONLY" = false ] && [ "$INSTALL_QUICKSHELL_ONLY" = false ]; then
    offer_custom_theme_install
  fi

  offer_wireguard_systemd_setup

  print_summary
  post_notes

  info "Done!"
}

main "$@"
