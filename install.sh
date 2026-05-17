#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
RUN_ID="$(date +%Y%m%d-%H%M%S)"
VSCODE_EXTENSION_SRC="$SCRIPT_DIR/hanauta/vscode-wallpaper-theme"
VSCODE_EXTENSION_ID="hanauta.hanauta-wallpaper-theme"
SWEET_CURSOR_THEME_NAME="sweet-cursors"
SWEET_CURSOR_THEME_SIZE="24"
SWEET_CURSOR_REPO_URL="https://github.com/Gigas002/Sweet.git"
SWEET_CURSOR_REPO_BRANCH="cursors"

INSTALL_EDITOR_EXTENSIONS_AUTO=false
INSTALL_VSCODE_ONLY=false
INSTALL_VSCODIUM_ONLY=false
INSTALL_NOTIFICATION_DAEMON_ONLY=false
INSTALL_QUICKSHELL_ONLY=false
INSTALL_WIREGUARD_SYSTEMD_ONLY=false
INSTALL_SDDM_ONLY=false
INSTALL_I3_VOLUME_ONLY=false
INSTALL_PRINTER_PLUGIN_ONLY=false
INSTALL_HANAUTA_SERVICE_ONLY=false
INSTALL_CUSTOM_THEMES=false
CUSTOM_THEMES_SELECTION=""
INSTALL_CUSTOM_THEMES_TO_SYSTEM=true
INSTALL_UPDATE_MODE=false
ENABLE_SAFETY_BACKUPS=true
INSTALL_CURSOR_ONLY=false
INSTALL_CURSOR_THEME_TO_SYSTEM=false
INSTALL_GTK_THEME_ONLY=false
INSTALL_RUBIK_FONT_ONLY=false
INSTALL_BLESH_ONLY=false
INSTALL_ZSH_THEME_ONLY=false
INSTALL_FISH_THEME_ONLY=false
GTK_THEME_SELECTION=""
ADW_GTK_REPO="lassekongo83/adw-gtk3"
I3_VOLUME_REPO_URL="https://github.com/hastinbe/i3-volume.git"
I3_VOLUME_REPO_BRANCH="master"
PRINTER_PLUGIN_REPO_URL="https://github.com/gab-luz/hanauta-plugin-printer"
PRINTER_PLUGIN_REPO_BRANCH="main"
PRINTER_PLUGIN_ID="printer_widget"
SAFETY_BACKUP_ROOT="${HOME}/.config/i3/backups/install-${RUN_ID}"

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

on_install_error() {
  local exit_code="$?"
  local line_no="${1:-unknown}"
  error "install.sh failed at line ${line_no} (exit ${exit_code})."
  if [ "${ENABLE_SAFETY_BACKUPS}" = true ]; then
    warn "Safety backups for this run are in: ${SAFETY_BACKUP_ROOT}"
  fi
  exit "$exit_code"
}

trap 'on_install_error $LINENO' ERR

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

resolve_uv_bin() {
  if need_cmd uv; then
    command -v uv
    return 0
  fi
  if [ -x "$HOME/.local/bin/uv" ]; then
    export PATH="$HOME/.local/bin:$PATH"
    printf '%s\n' "$HOME/.local/bin/uv"
    return 0
  fi
  return 1
}

ensure_uv_available() {
  if resolve_uv_bin >/dev/null 2>&1; then
    return 0
  fi
  info "Installing uv (fast Python package manager)..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
  if ! resolve_uv_bin >/dev/null 2>&1; then
    error "Failed to install uv"
    return 1
  fi
  success "uv is available"
}

run_privileged_cmd() {
  local reason="${1:-This action requires elevated privileges.}"
  shift || true
  local -a cmd=("$@")
  local bin=""

  if [ ${#cmd[@]} -eq 0 ]; then
    error "run_privileged_cmd called without command."
    return 1
  fi

  if [[ "${cmd[0]}" == */* ]]; then
    bin="${cmd[0]}"
  else
    bin="$(command -v "${cmd[0]}" 2>/dev/null || true)"
  fi

  if [ -z "$bin" ]; then
    error "Command not found: ${cmd[0]}"
    return 1
  fi
  cmd[0]="$bin"

  info "$reason"
  if [ "${EUID:-$(id -u)}" -eq 0 ]; then
    "${cmd[@]}"
    return $?
  fi

  if need_cmd sudo; then
    sudo "${cmd[@]}"
    return $?
  fi

  if need_cmd pkexec; then
    info "Using Polkit (pkexec) because package installation modifies system directories and needs root access."
    pkexec "${cmd[@]}"
    return $?
  fi

  error "No privilege escalation tool available (sudo/pkexec)."
  return 1
}

run_cmd_silencing_inkscape_stderr() {
  "$@" 2> >(
    while IFS= read -r line; do
      case "${line,,}" in
        *inkscape*)
          continue
          ;;
      esac
      printf '%s\n' "$line" >&2
    done
  )
}

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

normalize_cursor_theme_selection() {
  local raw="${1:-}"
  raw="$(printf '%s' "$raw" | tr '[:upper:]' '[:lower:]')"
  case "$raw" in
    sweet|sweet-cursors)
      printf '%s\n' "sweet-cursors"
      ;;
    *)
      return 1
      ;;
  esac
}

normalize_gtk_theme_selection() {
  local raw="${1:-}"
  raw="$(printf '%s' "$raw" | tr '[:upper:]' '[:lower:]')"
  case "$raw" in
    adw-gtk3|adw-gtk3-dark)
      printf '%s\n' "$raw"
      ;;
    *)
      return 1
      ;;
  esac
}

print_help() {
  cat <<EOF
Usage: ./install.sh [OPTIONS]

Without flags:
  Runs the full desktop install.

Options:
  -h, --help                    Show this help and exit
  --vscode                      Install only the VS Code extension
  --vscodium                    Install only the VSCodium extension
  --notification-daemon         Install only Hanauta notification daemon components
  --quickshell                  Install only Quickshell runtime dependencies
  --wireguard-systemd           Offer a systemd-based WireGuard auto-start setup
  --i3-volume                   Install only i3-volume + volnoti integration
  --printer-plugin              Install/update only the Hanauta printer plugin from git
  --hanauta-service            Install/update Hanauta root service unit only
  --sddm                        Install and configure SilentSDDM only
  --custom-themes               Install all vendored custom themes (retrowave + dracula)
  --custom-themes=NAME          Install custom themes by selection: retrowave, dracula, all
  --custom-themes-system        Force custom themes installation into /usr/share/themes too
  --cursor-theme=NAME           Install only cursor theme by name (supported: sweet-cursors)
  --cursor-theme-system         Also install cursor theme into /usr/share/icons using sudo
  --gtk-theme=NAME              Install only GTK theme by name (supported: adw-gtk3, adw-gtk3-dark)
  --rubik-font                  Install only bundled Rubik fonts (user + optional system-wide)
  --blesh                       Customize Bash prompt theme (ble.sh style) only
  --zsh                         Customize Zsh prompt theme only
  --fish                        Customize Fish prompt theme only
  --update                      Updater mode: preserve local state and avoid destructive replacements when possible
EOF
}

init_safety_backups() {
  if [ "${ENABLE_SAFETY_BACKUPS}" != true ]; then
    return 0
  fi
  mkdir -p "$SAFETY_BACKUP_ROOT"
}

backup_path_if_exists() {
  local path="$1"
  local label="${2:-path}"
  local base=""
  local backup_path=""

  [ "${ENABLE_SAFETY_BACKUPS}" = true ] || return 0
  [ -e "$path" ] || return 0

  init_safety_backups
  base="$(basename "$path")"
  backup_path="${SAFETY_BACKUP_ROOT}/${base}"
  if [ -e "$backup_path" ]; then
    backup_path="${backup_path}-$(date +%s)"
  fi
  cp -a "$path" "$backup_path"
  info "Safety backup (${label}): $path -> $backup_path"
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
  backup_path_if_exists "$target_dir" "$label extension"
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
      --i3-volume)
        INSTALL_I3_VOLUME_ONLY=true
        ;;
      --printer-plugin)
        INSTALL_PRINTER_PLUGIN_ONLY=true
        ;;
      --hanauta-service)
        INSTALL_HANAUTA_SERVICE_ONLY=true
        ;;
      --sddm)
        INSTALL_SDDM_ONLY=true
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
      --cursor-theme=*)
        INSTALL_CURSOR_ONLY=true
        SWEET_CURSOR_THEME_NAME="${1#*=}"
        ;;
      --cursor-theme-system)
        INSTALL_CURSOR_THEME_TO_SYSTEM=true
        ;;
      --gtk-theme=*)
        INSTALL_GTK_THEME_ONLY=true
        GTK_THEME_SELECTION="${1#*=}"
        ;;
      --rubik-font)
        INSTALL_RUBIK_FONT_ONLY=true
        ;;
      --blesh)
        INSTALL_BLESH_ONLY=true
        ;;
      --zsh)
        INSTALL_ZSH_THEME_ONLY=true
        ;;
      --fish)
        INSTALL_FISH_THEME_ONLY=true
        ;;
      --update)
        INSTALL_UPDATE_MODE=true
        ;;
      -h|--help)
        print_help
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

update_managed_block() {
  local file_path="$1"
  local marker="$2"
  local block_content="$3"
  local tmp_file=""
  local begin_marker="# >>> hanauta ${marker} >>>"
  local end_marker="# <<< hanauta ${marker} <<<"

  mkdir -p "$(dirname "$file_path")"
  touch "$file_path"
  backup_path_if_exists "$file_path" "$marker"

  tmp_file="$(mktemp)"
  awk -v begin="$begin_marker" -v end="$end_marker" '
    BEGIN { in_block=0 }
    $0 == begin { in_block=1; next }
    $0 == end { in_block=0; next }
    in_block == 0 { print }
  ' "$file_path" > "$tmp_file"

  mv "$tmp_file" "$file_path"

  {
    echo ""
    echo "$begin_marker"
    printf "%s\n" "$block_content"
    echo "$end_marker"
  } >> "$file_path"
}

install_bash_theme_blesh() {
  local bashrc="$HOME/.bashrc"
  local marker_file="$HOME/.local/state/hanauta/.blesh_nerd_font_hint_shown"
  local block_content=""
  block_content='if [ -f "$HOME/.local/share/blesh/out/ble.sh" ]; then
  source "$HOME/.local/share/blesh/out/ble.sh"
elif [ -f "$HOME/.local/share/blesh/ble.sh" ]; then
  source "$HOME/.local/share/blesh/ble.sh"
elif [ -f "/usr/share/blesh/out/ble.sh" ]; then
  source "/usr/share/blesh/out/ble.sh"
elif [ -f "/usr/share/blesh/ble.sh" ]; then
  source "/usr/share/blesh/ble.sh"
fi
if [ -n "${BLE_VERSION-}" ] && [ "${BLE_ATTACHED-}" != 1 ]; then
  ble-attach 2>/dev/null || true
fi

# Enable predictive completion behavior when ble.sh is active.
if [ -n "${BLE_VERSION-}" ]; then
  bleopt complete_auto_complete=1 2>/dev/null || true
  bleopt complete_menu_style=desc 2>/dev/null || true
  bleopt complete_ambiguous=1 2>/dev/null || true
  bleopt complete_auto_history=1 2>/dev/null || true
fi

# Load bash-completion when available for richer completion sources.
if [ -f "/usr/share/bash-completion/bash_completion" ]; then
  source "/usr/share/bash-completion/bash_completion"
elif [ -f "/etc/bash_completion" ]; then
  source "/etc/bash_completion"
fi

# Load git prompt helper if available so we can render branch/status in prompt.
if [ -z "${__git_ps1-}" ]; then
  if [ -f "/usr/lib/git-core/git-sh-prompt" ]; then
    source "/usr/lib/git-core/git-sh-prompt"
  elif [ -f "/usr/share/git/completion/git-prompt.sh" ]; then
    source "/usr/share/git/completion/git-prompt.sh"
  fi
fi

__hanauta_prompt_segment_git() {
  if declare -F __git_ps1 >/dev/null 2>&1; then
    __git_ps1 "%s"
  fi
}

__hanauta_prompt_segment_venv() {
  if [ -n "${VIRTUAL_ENV-}" ]; then
    printf "%s" "${VIRTUAL_ENV##*/}"
  fi
}

if [ -n "${BASH_VERSION-}" ] && [ "${TERM-}" != "dumb" ]; then
  GIT_PS1_SHOWDIRTYSTATE=1
  GIT_PS1_SHOWSTASHSTATE=1
  GIT_PS1_SHOWUNTRACKEDFILES=1

  __hanauta_nf_or_ascii() {
    local nf="$1"
    local ascii="$2"
    if [ "${HANAUTA_PROMPT_ASCII_ONLY:-0}" = "1" ]; then
      printf "%s" "$ascii"
    else
      printf "%s" "$nf"
    fi
  }

  __hanauta_render_prompt() {
    local last_exit="$?"
    local status_segment="" time_segment="" user_host_segment="" cwd_segment="" git_segment="" venv_segment="" top_line=""
    local icon_time icon_user icon_dir icon_git icon_venv sep_right prompt_symbol
    icon_time="$(__hanauta_nf_or_ascii "" "time")"
    icon_user="$(__hanauta_nf_or_ascii "" "user")"
    icon_dir="$(__hanauta_nf_or_ascii "" "dir")"
    icon_git="$(__hanauta_nf_or_ascii "" "git")"
    icon_venv="$(__hanauta_nf_or_ascii "" "venv")"
    sep_right="$(__hanauta_nf_or_ascii "" ">")"
    prompt_symbol="$(__hanauta_nf_or_ascii "❯" "$")"
    if [ "$last_exit" -ne 0 ]; then
      status_segment="\[\e[38;5;203m\][x:$last_exit]\[\e[0m\] "
    fi
    if [ "${EUID:-$(id -u)}" -eq 0 ]; then
      prompt_symbol="$(__hanauta_nf_or_ascii "" "#")"
    fi
    time_segment="\[\e[38;5;110m\]${icon_time} \A\[\e[0m\]"
    user_host_segment="\[\e[38;5;45m\]${icon_user} \u@\h\[\e[0m\]"
    cwd_segment="\[\e[38;5;81m\]${icon_dir} \w\[\e[0m\]"
    git_segment="$(__hanauta_prompt_segment_git)"
    if [ -n "$git_segment" ]; then
      git_segment="\[\e[38;5;214m\] ${icon_git} ${git_segment}\[\e[0m\]"
    fi
    venv_segment="$(__hanauta_prompt_segment_venv)"
    if [ -n "$venv_segment" ]; then
      venv_segment="\[\e[38;5;141m\] ${icon_venv} ${venv_segment}\[\e[0m\]"
    fi
    top_line="${status_segment}${time_segment} \[\e[38;5;244m\]${sep_right}\[\e[0m\] ${user_host_segment} \[\e[38;5;244m\]${sep_right}\[\e[0m\] ${cwd_segment}${git_segment}${venv_segment}"
    PS1="${top_line}\n\[\e[38;5;39m\]${prompt_symbol}\[\e[0m\] "
  }

  PROMPT_COMMAND="__hanauta_render_prompt${PROMPT_COMMAND:+;$PROMPT_COMMAND}"
fi'
  update_managed_block "$bashrc" "bash-theme-blesh" "$block_content"
  success "Bash theme customization applied to $bashrc"
  if [ ! -f "$marker_file" ]; then
    mkdir -p "$(dirname "$marker_file")"
    cat <<'EOF'
[INFO] For the best prompt rendering, set your terminal font to a Nerd Font.
[INFO] Recommended: MesloLGS NF (installed by this script).
[INFO] Kitty example: set `font_family MesloLGS NF` in ~/.config/kitty/kitty.conf
EOF
    : > "$marker_file"
  fi
  if [ ! -f "$HOME/.local/share/blesh/out/ble.sh" ] && \
     [ ! -f "$HOME/.local/share/blesh/ble.sh" ] && \
     [ ! -f "/usr/share/blesh/out/ble.sh" ] && \
     [ ! -f "/usr/share/blesh/ble.sh" ]; then
    warn "ble.sh not found after setup; applied prompt fallback only."
  fi
}

install_nerd_font_user() {
  local font_dir="$HOME/.local/share/fonts/MesloLGS_NF"
  local base_url="https://github.com/romkatv/powerlevel10k-media/raw/master"
  local -a files=(
    MesloLGS%20NF%20Regular.ttf
    MesloLGS%20NF%20Bold.ttf
    MesloLGS%20NF%20Italic.ttf
    MesloLGS%20NF%20Bold%20Italic.ttf
  )
  local file=""
  local target=""

  if ! need_cmd curl; then
    warn "curl not found; skipping Nerd Font download."
    return 0
  fi

  mkdir -p "$font_dir"
  for file in "${files[@]}"; do
    target="$font_dir/${file//%20/ }"
    if [ ! -f "$target" ]; then
      info "Installing Nerd Font file: ${file//%20/ }"
      if ! curl -fsSL -o "$target" "$base_url/$file"; then
        warn "Failed to download $file"
      fi
    fi
  done

  if need_cmd fc-cache; then
    fc-cache -f "$HOME/.local/share/fonts" >/dev/null 2>&1 || fc-cache -f >/dev/null 2>&1 || true
  fi
}

install_zsh_theme() {
  local zshrc="$HOME/.zshrc"
  local block_content=""
  block_content='autoload -Uz colors && colors
setopt PROMPT_SUBST
PROMPT="%F{45}%n@%m%f %F{81}%~%f %# "'
  update_managed_block "$zshrc" "zsh-theme" "$block_content"
  success "Zsh theme customization applied to $zshrc"
}

install_fish_theme() {
  local fish_conf="$HOME/.config/fish/config.fish"
  local block_content=""
  block_content='function fish_prompt
    set_color 45
    printf "%s@%s " $USER (prompt_hostname)
    set_color 81
    printf "%s" (prompt_pwd)
    set_color normal
    printf " > "
end'
  update_managed_block "$fish_conf" "fish-theme" "$block_content"
  success "Fish theme customization applied to $fish_conf"
}

install_blesh_from_official_repo() {
  local target_dir="$HOME/.local/share/blesh"
  local tmp_root=""
  local repo_dir=""
  local make_bin=""
  local build_log=""
  local install_log=""

  if ! need_cmd git; then
    warn "git is required to install ble.sh from the official repository."
    return 1
  fi
  if need_cmd gmake; then
    make_bin="gmake"
  elif need_cmd make; then
    make_bin="make"
  else
    warn "GNU make is required to build ble.sh."
    return 1
  fi

  tmp_root="$(mktemp -d)"
  repo_dir="$tmp_root/ble.sh"
  build_log="$tmp_root/ble-build.log"
  install_log="$tmp_root/ble-install.log"

  info "Cloning official ble.sh repository..."
  if ! git clone --depth 1 https://github.com/akinomyoga/ble.sh.git "$repo_dir" >/dev/null 2>&1; then
    rm -rf "$tmp_root"
    warn "Failed to clone ble.sh official repository."
    return 1
  fi

  info "Building ble.sh runtime files..."
  if ! "$make_bin" -C "$repo_dir" -f GNUmakefile build >"$build_log" 2>&1; then
    warn "Failed to build ble.sh runtime files."
    if [ -s "$build_log" ]; then
      warn "ble.sh build log (last lines):"
      tail -n 20 "$build_log" >&2 || true
    fi
    return 1
  fi

  if [ ! -f "$repo_dir/out/ble.sh" ] || [ ! -f "$repo_dir/out/lib/init-term.sh" ]; then
    warn "ble.sh build finished but required runtime files are missing in out/."
    return 1
  fi

  mkdir -p "$(dirname "$target_dir")"
  rm -rf "$target_dir"
  info "Installing ble.sh into $target_dir..."
  if ! "$make_bin" -C "$repo_dir" -f GNUmakefile install INSDIR="$target_dir" >"$install_log" 2>&1; then
    warn "Failed to install ble.sh runtime files."
    if [ -s "$install_log" ]; then
      warn "ble.sh install log (last lines):"
      tail -n 20 "$install_log" >&2 || true
    fi
    return 1
  fi
  # Ensure the runtime layout used by our bashrc source path always exists.
  mkdir -p "$target_dir/out"
  rsync -a "$repo_dir/out/" "$target_dir/out/" >/dev/null 2>&1 || true
  if [ -f "$repo_dir/out/ble.sh" ]; then
    cp -f "$repo_dir/out/ble.sh" "$target_dir/ble.sh" >/dev/null 2>&1 || true
  fi
  # Keep top-level docs/helpers for local inspection; runtime comes from make install.
  rsync -a --delete --exclude '.git' --exclude 'out' "$repo_dir/" "$target_dir/" >/dev/null 2>&1 || true
  rm -rf "$tmp_root"

  success "ble.sh installed to $target_dir"
  return 0
}

blesh_install_is_usable() {
  local base="$1"
  # Accept both layouts:
  # 1) out/ble.sh + out/lib/* (build-tree style)
  # 2) ble.sh + lib/*        (make install INSDIR style)
  if [ -f "$base/out/ble.sh" ] &&
     [ -f "$base/out/lib/init-term.sh" ] &&
     [ -f "$base/out/lib/core-cmdspec.sh" ] &&
     [ -f "$base/out/lib/init-cmap.sh" ] &&
     [ -f "$base/out/lib/init-bind.sh" ]; then
    return 0
  fi

  if [ -f "$base/out/ble.sh" ] &&
     [ -f "$base/lib/init-term.sh" ] &&
     [ -f "$base/lib/core-cmdspec.sh" ] &&
     [ -f "$base/lib/init-cmap.sh" ] &&
     [ -f "$base/lib/init-bind.sh" ]; then
    return 0
  fi

  if [ -f "$base/ble.sh" ] &&
     [ -f "$base/lib/init-term.sh" ] &&
     [ -f "$base/lib/core-cmdspec.sh" ] &&
     [ -f "$base/lib/init-cmap.sh" ] &&
     [ -f "$base/lib/init-bind.sh" ]; then
    return 0
  fi

  return 1
}

ensure_shell_theme_dependency() {
  local target="$1"

  case "$target" in
    blesh)
      install_nerd_font_user

      if ! need_cmd gawk; then
        info "GNU awk (gawk) is required for ble.sh; installing it first..."
        if detect_debian_like; then
          echo -e "${CYAN}[*]${NC} Updating package lists..."
          sudo apt-get update -qq
          install_apt_group "ble.sh dependency" gawk
        elif detect_arch; then
          install_pacman_group "ble.sh dependency" gawk
        else
          warn "Unknown distro. Auto-install for gawk is supported only on Debian-like and Arch Linux."
          return 1
        fi
        if ! need_cmd gawk; then
          warn "gawk is still unavailable; cannot continue with ble.sh setup."
          return 1
        fi
      fi

      if blesh_install_is_usable "$HOME/.local/share/blesh" || \
         blesh_install_is_usable "/usr/share/blesh" || \
         [ -f "$HOME/.local/share/blesh/ble.sh" ] || \
         [ -f "/usr/share/blesh/ble.sh" ]; then
        return 0
      fi
      if [ -f "$HOME/.local/share/blesh/out/ble.sh" ] && ! blesh_install_is_usable "$HOME/.local/share/blesh"; then
        warn "Existing ble.sh install looks incomplete; repairing it now."
        install_blesh_from_official_repo || return 1
        if blesh_install_is_usable "$HOME/.local/share/blesh"; then
          return 0
        fi
      fi
      if ! confirm_yes "ble.sh was not found. Install it now from the official GitHub repo?"; then
        warn "ble.sh is required for --blesh customization. Skipping."
        return 1
      fi
      install_blesh_from_official_repo || return 1
      if blesh_install_is_usable "$HOME/.local/share/blesh" || \
         blesh_install_is_usable "/usr/share/blesh" || \
         [ -f "$HOME/.local/share/blesh/ble.sh" ] || \
         [ -f "/usr/share/blesh/ble.sh" ]; then
        return 0
      fi
      warn "ble.sh is still not available after install attempt."
      return 1
      ;;
    zsh)
      if need_cmd zsh; then
        return 0
      fi
      if ! confirm_yes "zsh is not installed. Install it now?"; then
        warn "zsh is required for --zsh customization. Skipping."
        return 1
      fi
      if detect_debian_like; then
        echo -e "${CYAN}[*]${NC} Updating package lists..."
        sudo apt-get update -qq
        install_apt_group "zsh shell dependency" zsh
      elif detect_arch; then
        install_pacman_group "zsh shell dependency" zsh
      else
        warn "Unknown distro. Auto-install is supported only on Debian-like and Arch Linux."
        return 1
      fi
      need_cmd zsh
      return $?
      ;;
    fish)
      if need_cmd fish; then
        return 0
      fi
      if ! confirm_yes "fish is not installed. Install it now?"; then
        warn "fish is required for --fish customization. Skipping."
        return 1
      fi
      if detect_debian_like; then
        echo -e "${CYAN}[*]${NC} Updating package lists..."
        sudo apt-get update -qq
        install_apt_group "fish shell dependency" fish
      elif detect_arch; then
        install_pacman_group "fish shell dependency" fish
      else
        warn "Unknown distro. Auto-install is supported only on Debian-like and Arch Linux."
        return 1
      fi
      need_cmd fish
      return $?
      ;;
    *)
      warn "Unknown shell dependency target: $target"
      return 1
      ;;
  esac
}

offer_shell_theme_customization() {
  local choice=""
  echo ""
  echo -e "${MAGENTA}${BOLD}Optional Shell Theme Customization${NC}"
  echo -e "Apply prompt theme customization for ${BOLD}Bash (ble.sh style)${NC}, ${BOLD}Zsh${NC}, or ${BOLD}Fish${NC}."
  echo ""

  if ! confirm_yes "Do you want to customize shell themes now?"; then
    info "Skipping shell theme customization."
    return 0
  fi

  echo "Choose a shell to customize:"
  echo "  1. Bash (ble.sh style)"
  echo "  2. Zsh"
  echo "  3. Fish"
  echo "  4. Skip"
  read -r -p "Select [1-4]: " choice
  case "$choice" in
    1) ensure_shell_theme_dependency blesh && install_bash_theme_blesh ;;
    2) ensure_shell_theme_dependency zsh && install_zsh_theme ;;
    3) ensure_shell_theme_dependency fish && install_fish_theme ;;
    4) info "Skipped shell theme customization." ;;
    *) warn "Unknown selection. Skipping shell theme customization." ;;
  esac
}

install_rubik_fonts() {
  local fonts_src_root="$SCRIPT_DIR/assets/fonts"
  local user_dest_root="$HOME/.local/share/fonts/Rubik"
  local system_dest_root="/usr/local/share/fonts/Rubik"
  local system_share_dest_root="/usr/share/fonts/Rubik"
  local -a rubik_files=(
    Rubik-VariableFont_wght.ttf
    Rubik-Italic-VariableFont_wght.ttf
  )
  local file=""
  local user_has_all=true
  local system_has_all=true
  local system_share_has_all=true

  if [ ! -d "$fonts_src_root" ]; then
    warn "Font source directory not found: $fonts_src_root"
    return 1
  fi

  for file in "${rubik_files[@]}"; do
    if [ ! -f "$fonts_src_root/$file" ]; then
      warn "Missing bundled Rubik font file: $fonts_src_root/$file"
      return 1
    fi
  done

  for file in "${rubik_files[@]}"; do
    [ -f "$user_dest_root/$file" ] || user_has_all=false
    [ -f "$system_dest_root/$file" ] || system_has_all=false
    [ -f "$system_share_dest_root/$file" ] || system_share_has_all=false
  done

  if [ "$user_has_all" = true ]; then
    info "Rubik fonts already installed for user at $user_dest_root"
  else
    mkdir -p "$user_dest_root"
    for file in "${rubik_files[@]}"; do
      cp -f "$fonts_src_root/$file" "$user_dest_root/"
    done
    success "Rubik fonts installed for user at $user_dest_root"
  fi

  if need_cmd fc-cache; then
    fc-cache -f "$HOME/.local/share/fonts" >/dev/null 2>&1 || fc-cache -f >/dev/null 2>&1 || true
  fi

  if [ "$system_has_all" = true ] || [ "$system_share_has_all" = true ]; then
    info "Rubik fonts already installed system-wide; skipping system install prompt."
    return 0
  fi

  if [ "$user_has_all" = true ]; then
    info "Rubik fonts are already installed in user fonts; skipping system install prompt."
    return 0
  fi

  if ! confirm_default_yes "Also install Rubik fonts system-wide to $system_dest_root using sudo?"; then
    info "Skipped system-wide Rubik font installation."
    return 0
  fi

  if ! need_cmd sudo; then
    warn "sudo not found; skipping system-wide Rubik font installation."
    return 0
  fi

  sudo mkdir -p "$system_dest_root"
  for file in "${rubik_files[@]}"; do
    sudo cp -f "$fonts_src_root/$file" "$system_dest_root/"
  done
  success "Rubik fonts installed system-wide at $system_dest_root"

  if need_cmd fc-cache; then
    sudo fc-cache -f /usr/local/share/fonts >/dev/null 2>&1 || sudo fc-cache -f >/dev/null 2>&1 || true
  fi
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
    warn "Expected /etc/wireguard/${iface}.conf but it was not found. Skipping."
    return 0
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
  if need_cmd systemctl; then
    if systemctl list-unit-files 'wg-quick@*.service' --no-legend 2>/dev/null | awk '$2=="enabled"{found=1} END{exit(found?0:1)}'; then
      info "WireGuard systemd auto-start is already enabled; skipping optional WireGuard prompt."
      return 0
    fi
  fi

  echo ""
  echo -e "${MAGENTA}${BOLD}Optional WireGuard Setup${NC}"
  echo -e "Continuing will enable ${BOLD}WireGuard VPN auto-start on login/boot${NC} for one interface."
  echo -e "This uses ${BOLD}sudo${NC}, enables ${BOLD}wg-quick@interface.service${NC}, and may reconnect VPN outside the i3 session."
  echo -e "If you do ${BOLD}not${NC} use WireGuard, choose ${BOLD}No${NC} in the next prompt."
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

install_sddm_packages_debian() {
  local svg_pkg=""
  local vkb_pkg=""
  local mm_pkg=""

  echo -e "${CYAN}[*]${NC} Updating package lists..."
  sudo apt-get update -qq

  install_apt_group "SilentSDDM base" sddm

  svg_pkg="$(pick_first_available_apt_package libqt6svg6 qt6-svg-dev)" || true
  vkb_pkg="$(pick_first_available_apt_package qml6-module-qtquick-virtualkeyboard qt6-virtualkeyboard-dev)" || true
  mm_pkg="$(pick_first_available_apt_package qml6-module-qtmultimedia qt6-multimedia-dev)" || true

  if [ -n "$svg_pkg" ]; then
    install_apt_group "SilentSDDM Qt SVG runtime" "$svg_pkg"
  else
    warn "No Debian package found for Qt6 SVG runtime (needed by SilentSDDM)."
  fi

  if [ -n "$vkb_pkg" ]; then
    install_apt_group "SilentSDDM virtual keyboard runtime" "$vkb_pkg"
  else
    warn "No Debian package found for Qt6 virtual keyboard runtime (needed by SilentSDDM)."
  fi

  if [ -n "$mm_pkg" ]; then
    install_apt_group "SilentSDDM multimedia runtime" "$mm_pkg"
  else
    warn "No Debian package found for Qt6 multimedia runtime (needed by SilentSDDM)."
  fi

  info "If your package manager prompts for a display manager, choose SDDM on that screen."
}

install_sddm_packages_arch() {
  install_pacman_group "SilentSDDM dependencies" \
    sddm qt6-svg qt6-virtualkeyboard qt6-multimedia-ffmpeg

  info "SDDM packages installed. We'll set sddm.service as the active display manager next."
}

set_sddm_as_default_display_manager() {
  if ! need_cmd sudo; then
    warn "sudo not found; cannot auto-set SDDM as default display manager."
    return 0
  fi

  if detect_debian_like; then
    local dm_file="/etc/X11/default-display-manager"
    local sddm_path=""
    sddm_path="$(command -v sddm 2>/dev/null || true)"
    if [ -z "$sddm_path" ]; then
      sddm_path="/usr/bin/sddm"
    fi
    info "Setting default display manager to SDDM (Debian/Ubuntu)..."
    printf '%s\n' "$sddm_path" | sudo tee "$dm_file" >/dev/null || true
    if need_cmd debconf-set-selections; then
      printf 'sddm shared/default-x-display-manager select sddm\n' | sudo debconf-set-selections || true
    fi
    success "Default display manager preference set to SDDM."
    return 0
  fi

  if detect_arch; then
    if need_cmd systemctl; then
      info "Setting default display manager to SDDM (Arch Linux)..."
      sudo systemctl disable gdm.service lightdm.service lxdm.service ly.service xdm.service >/dev/null 2>&1 || true
      sudo systemctl enable sddm.service >/dev/null 2>&1 || true
      success "sddm.service enabled as default display manager."
    fi
    return 0
  fi

  warn "Unknown distro: please choose SDDM as your display manager if prompted."
  return 0
}

check_sddm_version_requirement() {
  local detected=""
  local major=0
  local minor=0

  if ! need_cmd sddm; then
    warn "SDDM command not found after package installation."
    return 0
  fi

  detected="$(sddm --version 2>/dev/null | head -n 1 | grep -Eo '[0-9]+(\.[0-9]+){1,2}' | head -n 1 || true)"
  if [ -z "$detected" ]; then
    warn "Could not detect SDDM version. SilentSDDM requires SDDM >= 0.21.0."
    return 0
  fi

  major="${detected%%.*}"
  minor="$(printf '%s' "$detected" | cut -d. -f2)"
  minor="${minor:-0}"
  if [ "$major" -eq 0 ] && [ "$minor" -lt 21 ]; then
    warn "Detected SDDM $detected. SilentSDDM requires SDDM >= 0.21.0."
  else
    info "Detected SDDM version $detected (meets SilentSDDM requirement >= 0.21.0)."
  fi
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
    function print_key() {
      print key "=" value
    }
    /^\[.*\]$/ {
      if (in_section && !key_written) {
        print_key()
        key_written = 1
      }
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
        if (!key_written) {
          print_key()
          key_written = 1
        }
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

configure_sddm_for_silent_theme() {
  local conf_file="/etc/sddm.conf"
  local tmp_conf=""
  local backup_file=""

  if ! need_cmd sudo; then
    error "sudo is required to configure SDDM."
    return 1
  fi

  tmp_conf="$(mktemp)"
  if [ -f "$conf_file" ]; then
    sudo cp "$conf_file" "$tmp_conf"
    backup_file="/etc/sddm.conf.backup-$(date +%Y%m%d-%H%M%S)"
    sudo cp "$conf_file" "$backup_file"
    info "Backed up existing SDDM config to $backup_file"
  else
    : > "$tmp_conf"
  fi

  set_ini_key "$tmp_conf" "Theme" "Current" "silent"
  set_ini_key "$tmp_conf" "General" "InputMethod" "qtvirtualkeyboard"
  set_ini_key "$tmp_conf" "General" "GreeterEnvironment" "QML2_IMPORT_PATH=/usr/share/sddm/themes/silent/components/,QT_IM_MODULE=qtvirtualkeyboard"

  sudo mkdir -p /etc
  sudo cp "$tmp_conf" "$conf_file"
  rm -f "$tmp_conf"
  success "Configured /etc/sddm.conf for SilentSDDM"
}

install_silent_sddm_theme_files() {
  local tmp_root=""
  local repo_root=""
  local theme_dst="/usr/share/sddm/themes/silent"
  local fonts_src=""

  if ! need_cmd git; then
    error "git is required to install SilentSDDM."
    return 1
  fi
  if ! need_cmd sudo; then
    error "sudo is required to install SilentSDDM files."
    return 1
  fi

  tmp_root="$(mktemp -d)"
  repo_root="$tmp_root/SilentSDDM"
  info "Cloning SilentSDDM..."
  if ! git clone --depth 1 --branch main https://github.com/uiriansan/SilentSDDM "$repo_root" >/dev/null 2>&1; then
    rm -rf "$tmp_root"
    error "Failed to clone SilentSDDM repository."
    return 1
  fi

  info "Installing SilentSDDM theme files to $theme_dst..."
  sudo mkdir -p "$theme_dst"
  sudo rsync -a --delete --exclude '.git' "$repo_root/" "$theme_dst/"
  success "SilentSDDM theme files installed"

  fonts_src="$theme_dst/fonts"
  if [ -d "$fonts_src" ]; then
    info "Installing SilentSDDM bundled fonts..."
    sudo mkdir -p /usr/share/fonts
    sudo rsync -a "$fonts_src/" /usr/share/fonts/
    if need_cmd fc-cache; then
      sudo fc-cache -f /usr/share/fonts >/dev/null 2>&1 || sudo fc-cache -f >/dev/null 2>&1 || true
    fi
    success "SilentSDDM fonts installed"
  else
    warn "No fonts directory found in SilentSDDM theme."
  fi

  rm -rf "$tmp_root"
}

offer_sddm_service_enable() {
  if ! need_cmd systemctl; then
    warn "systemctl not found; skipping SDDM service enable/start."
    return 0
  fi
  if ! need_cmd sudo; then
    warn "sudo not found; skipping SDDM service enable/start."
    return 0
  fi

  disable_conflicting_display_managers

  if confirm_default_yes "Enable SDDM at boot with systemd now?"; then
    sudo systemctl enable sddm.service
    success "Enabled sddm.service"
  else
    info "Skipped enabling sddm.service."
  fi

  echo -e "${RED}${BOLD}[DANGER]${NC} ${RED}Starting SDDM right now can immediately end your current graphical session.${NC}"
  echo -e "${RED}If you continue, open apps or unsaved documents may be lost.${NC}"
  if confirm_yes "Start SDDM right now?"; then
    sudo systemctl restart sddm.service
    success "SDDM restarted"
  else
    info "Skipped starting SDDM right now."
  fi
}

disable_conflicting_display_managers() {
  local -a dms=(lightdm gdm gdm3 lxdm xdm ly)
  local dm=""
  local had_conflicts=false
  local -a active_conflicts=()

  if ! need_cmd systemctl; then
    return 0
  fi

  for dm in "${dms[@]}"; do
    if ! systemctl list-unit-files --type=service | awk '{print $1}' | grep -qx "${dm}.service"; then
      continue
    fi

    if systemctl is-enabled "${dm}.service" >/dev/null 2>&1 || systemctl is-active "${dm}.service" >/dev/null 2>&1; then
      had_conflicts=true
      warn "Disabling conflicting display manager: ${dm}.service"
      sudo systemctl disable "${dm}.service" >/dev/null 2>&1 || true
      success "Conflicting display manager disabled: ${dm}.service"

      if systemctl is-active "${dm}.service" >/dev/null 2>&1; then
        active_conflicts+=("${dm}.service")
      fi
    fi
  done

  if [ "$had_conflicts" = true ]; then
    info "Conflicting display managers were disabled so only SDDM starts at boot."
  fi

  if [ ${#active_conflicts[@]} -gt 0 ]; then
    warn "These display managers are still running in the current session: ${active_conflicts[*]}"
    warn "Stopping them now can immediately close your graphical session and lose unsaved work."
    if confirm_yes "Stop active conflicting display managers now anyway?"; then
      for dm in "${active_conflicts[@]}"; do
        sudo systemctl stop "$dm" >/dev/null 2>&1 || true
        success "Stopped $dm"
      done
    else
      info "Keeping current display manager process running. Changes will apply cleanly on next reboot."
    fi
  fi
}

install_silent_sddm() {
  if ! need_cmd sudo; then
    error "sudo is required for SilentSDDM installation."
    return 1
  fi

  if detect_debian_like; then
    info "Installing SilentSDDM dependencies for Debian-based distro..."
    install_sddm_packages_debian
  elif detect_arch; then
    info "Installing SilentSDDM dependencies for Arch Linux..."
    install_sddm_packages_arch
  else
    warn "Unknown distro; skipping dependency install. Theme files and config will still be applied."
  fi

  check_sddm_version_requirement
  set_sddm_as_default_display_manager
  install_silent_sddm_theme_files
  configure_sddm_for_silent_theme
  offer_sddm_service_enable
  success "SilentSDDM installation and configuration finished"
}

offer_silent_sddm_install() {
  if need_cmd sddm && [ -d "/usr/share/sddm/themes/silent" ] && \
     [ -f "/etc/sddm.conf" ] && \
     rg -q '^[[:space:]]*Current[[:space:]]*=[[:space:]]*silent[[:space:]]*$' /etc/sddm.conf 2>/dev/null; then
    info "SilentSDDM is already installed and configured; skipping optional SDDM prompt."
    return 0
  fi

  echo ""
  echo -e "${MAGENTA}${BOLD}Optional SDDM Setup (SilentSDDM)${NC}"
  echo -e "Install and configure ${BOLD}SDDM + SilentSDDM${NC} as your login manager."
  echo -e "This is a ${BOLD}system-level change${NC} and may affect login behavior."
  echo -e "If an installer prompt appears asking for display manager selection, choose ${BOLD}SDDM${NC}."
  echo -e "Hanauta will also try to set SDDM as the default automatically."
  echo ""

  if ! confirm_yes "Do you want to install and configure SilentSDDM now?"; then
    info "Skipping SilentSDDM installation."
    return 0
  fi
  if ! confirm_yes "Are you absolutely sure you want to apply this SDDM login manager setup?"; then
    info "Second confirmation declined. Skipping SilentSDDM installation."
    return 0
  fi

  install_silent_sddm
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
  ensure_uv_available || return 1
  
  if ! python3 -c "import rich" 2>/dev/null; then
    info "Installing rich for colorful output..."
    uv pip install --system rich --quiet 2>/dev/null || true
  fi
}

setup_python_venv() {
  local venv_dir="$SCRIPT_DIR/.venv"
  
  ensure_uv_available || return 1

  if [ -d "$venv_dir" ]; then
    info "Python venv already exists; syncing dependencies..."
  else
    info "Creating Python virtual environment..."
    uv venv "$venv_dir"
  fi

  info "Installing Python dependencies from pyproject.toml..."
  cd "$SCRIPT_DIR"
  uv_sync_with_recovery
  
  success "Python environment ready"
}

install_pycups_build_dependencies() {
  if detect_debian_like; then
    if dpkg -s libcups2-dev >/dev/null 2>&1; then
      info "libcups2-dev already installed."
      return 0
    fi
    run_privileged_cmd \
      "Installing libcups2-dev so pycups can compile against CUPS headers (cups/http.h)." \
      apt-get update -qq
    run_privileged_cmd \
      "Installing libcups2-dev so pycups can compile against CUPS headers (cups/http.h)." \
      apt-get install -y libcups2-dev
    return $?
  fi

  if detect_arch; then
    if pacman -Q cups >/dev/null 2>&1; then
      info "cups package already installed."
      return 0
    fi
    run_privileged_cmd \
      "Installing cups so pycups can compile against CUPS headers (cups/http.h)." \
      pacman -S --needed --noconfirm cups
    return $?
  fi

  warn "Unknown distro: cannot auto-install pycups build headers."
  return 1
}

uv_sync_with_recovery() {
  local sync_log=""
  sync_log="$(mktemp)"

  if uv sync 2> >(tee "$sync_log" >&2); then
    rm -f "$sync_log"
    return 0
  fi

  if rg -q "cups/http.h|Failed to build.*pycups|pycups==|fatal error: .*cups/" "$sync_log" 2>/dev/null; then
    warn "Detected pycups build failure caused by missing CUPS development headers."
    if install_pycups_build_dependencies; then
      info "Retrying uv sync after installing CUPS development packages..."
      if uv sync; then
        rm -f "$sync_log"
        return 0
      fi
    fi
  fi

  rm -f "$sync_log"
  error "uv sync failed."
  return 1
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
    git
    ripgrep
    xorg xinit
    i3-wm rofi feh picom
    x11-xserver-utils x11-utils xdotool xclip
    jq curl ffmpeg rsync
    gawk
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
    libcups2-dev
    libglib2.0-dev libgtk-3-dev
    qt6-base-dev
    qt6-declarative-dev
    libxkbcommon-x11-0
    libxcb-cursor0
    sassc
    inkscape
    x11-apps
    xdg-user-dirs
    libgtk-3-bin
    dbus-x11
    bc
  )
  local -a optional_pkgs=(
    copyq clipit plank ukui-window-switch
    kdeconnect qt6-tools-dev-tools     polkitd
  )

  echo -e "${CYAN}[*]${NC} Updating package lists..."
  sudo apt-get update -qq

  install_apt_group "core desktop stack" "${core_pkgs[@]}"
  install_apt_group "optional integrations" "${optional_pkgs[@]}"
  success "System packages installed"
}

install_packages_arch() {
  local -a core_pkgs=(
    git
    ripgrep
    xorg-server xorg-xinit
    i3-wm rofi feh picom
    xorg-xrandr xorg-xsetroot xorg-xwininfo xorg-xev xorg-xrdb xdotool xclip
    jq curl ffmpeg rsync
    gawk
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
    cups
    qt6-base
    qt6-declarative
    libxkbcommon-x11
    libxcb-cursor
    sassc
    inkscape
    xorg-xcursorgen
    xdg-user-dirs
    gtk3
    bc
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

install_hanauta_service_root() {
  local root="$HOME/.config/i3"
  local src_bin="$root/hanauta/bin/hanauta-service"
  local dst_bin="/usr/local/bin/hanauta-service"
  local unit="/etc/systemd/system/hanauta-service-root.service"
  local runtime_user="${SUDO_USER:-$USER}"

  if [ ! -x "$src_bin" ]; then
    warn "hanauta-service binary not found at $src_bin. Building services first..."
    build_native_services || return 1
  fi
  if [ ! -x "$src_bin" ]; then
    error "hanauta-service binary is still missing after build."
    return 1
  fi

  run_privileged_cmd \
    "Installing Hanauta root service binary to $dst_bin." \
    install -D -m 0755 "$src_bin" "$dst_bin" || return 1

  local unit_content=""
  unit_content="[Unit]
Description=Hanauta Root Service
After=network.target

[Service]
Type=simple
ExecStart=$dst_bin
Restart=always
RestartSec=2
User=root
Environment=HOME=/home/$runtime_user
Environment=HANAUTA_SETTINGS_PATH=/home/$runtime_user/.local/state/hanauta/notification-center/settings.json
Environment=HANAUTA_SERVICE_STATE_DIR=/home/$runtime_user/.local/state/hanauta/service

[Install]
WantedBy=multi-user.target"

  local tmp_unit
  tmp_unit="$(mktemp)"
  printf '%s\n' "$unit_content" > "$tmp_unit"
  run_privileged_cmd \
    "Installing Hanauta root service unit." \
    install -D -m 0644 "$tmp_unit" "$unit" || { rm -f "$tmp_unit"; return 1; }
  rm -f "$tmp_unit"

  run_privileged_cmd \
    "Reloading systemd and enabling hanauta-service-root.service." \
    systemctl daemon-reload || return 1
  run_privileged_cmd \
    "Enabling and starting hanauta-service-root.service." \
    systemctl enable --now hanauta-service-root.service || return 1

  success "Hanauta root service installed and active: hanauta-service-root.service"
}

copy_dotfiles() {
  local target="$HOME/.config/i3"
  local dry_run_output=""

  mkdir -p "$target"
  dry_run_output="$(rsync -ani \
    --exclude '.git' \
    --exclude 'backups' \
    --exclude 'install.sh' \
    "$SCRIPT_DIR/" \
    "$target/" || true)"

  if [ -z "$dry_run_output" ]; then
    success "Dotfiles already up to date; skipping copy"
    return 0
  fi

  if [ -d "$target" ] && [ ! -L "$target" ]; then
    local backup="$HOME/.config/i3.backup-$(date +%Y%m%d-%H%M%S)"
    info "Backing up existing i3 config to $backup"
    mkdir -p "$backup"
    rsync -a "$target/" "$backup/"
  fi

  info "Copying dotfiles..."
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

install_volnoti_build_deps_debian() {
  local pixbuf_dev_pkg=""

  echo -e "${CYAN}[*]${NC} Updating package lists..."
  sudo apt-get update -qq
  install_apt_group "volnoti source build deps" \
    git build-essential pkg-config autoconf automake libtool \
    libdbus-1-dev libdbus-glib-1-dev libgtk2.0-dev

  pixbuf_dev_pkg="$(pick_first_available_apt_package libgdk-pixbuf-2.0-dev libgdk-pixbuf2.0-dev)" || true
  if [ -n "$pixbuf_dev_pkg" ]; then
    install_apt_group "volnoti gdk-pixbuf dev" "$pixbuf_dev_pkg"
  else
    warn "No Debian package found for GDK Pixbuf development headers."
  fi
}

install_volnoti_build_deps_arch() {
  install_pacman_group "volnoti source build deps" \
    git base-devel pkgconf autoconf automake libtool dbus dbus-glib gtk2 gdk-pixbuf2
}

build_and_install_volnoti_from_source() {
  local tmp_root=""
  local repo_root=""

  if ! need_cmd git; then
    error "git is required to build volnoti from source."
    return 1
  fi
  if ! need_cmd sudo; then
    error "sudo is required to install volnoti to /usr."
    return 1
  fi

  tmp_root="$(mktemp -d)"
  repo_root="$tmp_root/volnoti"

  info "Cloning volnoti source..."
  if ! git clone --depth 1 https://github.com/brazdil/volnoti.git "$repo_root" >/dev/null 2>&1; then
    rm -rf "$tmp_root"
    error "Failed to clone volnoti repository."
    return 1
  fi

  # Upstream compatibility patch:
  # newer generated DBus client stubs accept notify(proxy, volume, error)
  # while some source snapshots still call notify(proxy, volume, muted, error).
  if [ -f "$repo_root/src/client.c" ] && [ -f "$repo_root/src/value-client-stub.h" ]; then
    if grep -q 'GError \*\*error)' "$repo_root/src/value-client-stub.h" 2>/dev/null; then
      perl -i -pe 's/\buk_ac_cam_db538_VolumeNotification_notify\s*\([^)]+\);/uk_ac_cam_db538_VolumeNotification_notify(proxy, volume, \&error);/g' "$repo_root/src/client.c"
    fi
  fi

  info "Building volnoti from source..."
  if ! (cd "$repo_root" && ./prepare.sh && ./configure --prefix=/usr && make); then
    rm -rf "$tmp_root"
    error "Failed to build volnoti from source."
    return 1
  fi

  info "Installing volnoti system-wide..."
  if ! (cd "$repo_root" && sudo make install); then
    rm -rf "$tmp_root"
    error "Failed to install volnoti from source."
    return 1
  fi

  rm -rf "$tmp_root"
  success "volnoti installed from source"
}

run_missing_component_installer() {
  local cmd_name="$1"
  local script_path="$2"
  local label="$3"

  if need_cmd "$cmd_name"; then
    info "$label is already installed"
    return 0
  fi

  if [ ! -x "$script_path" ]; then
    error "$label installer not found or not executable: $script_path"
    return 1
  fi

  info "$label is missing; running installer script..."
  "$script_path"
  if need_cmd "$cmd_name"; then
    success "$label is now available"
    return 0
  fi

  error "$label is still unavailable after running installer script."
  return 1
}

ensure_volnoti_available() {
  run_missing_component_installer \
    "volnoti" \
    "$HOME/.config/i3/hanauta/scripts/install_volnoti.sh" \
    "volnoti"
}

ensure_betterlockscreen_available() {
  run_missing_component_installer \
    "betterlockscreen" \
    "$HOME/.config/i3/hanauta/scripts/install_betterlockscreen.sh" \
    "betterlockscreen"
}

apply_i3_volume_compat_patches() {
  local repo_root="${1:?repo path is required}"
  local audio_file="$repo_root/lib/audio.sh"
  local output_file="$repo_root/lib/output.sh"
  local volnoti_plugin="$repo_root/plugins/notify/volnoti"

  if [ -f "$audio_file" ]; then
    perl -0pi -e 's@get_volume\(\) \{ wpctl get-volume "\$NODE_ID" \| awk '\''\{printf "%.2f", \$2 \* 100\}'\''; \}@get_volume() {\n    local raw\n    raw=\$(wpctl get-volume "\$NODE_ID" 2>/dev/null | awk '\''{print \$2}'\'')\n    if [[ "\$raw" =~ ^[0-9]+([.][0-9]+)?\$ ]]; then\n        awk -v v="\$raw" '\''BEGIN { printf "%.2f", v * 100 }'\''\n    else\n        # Always return a valid numeric value for downstream formatters.\n        echo "0.00"\n    fi\n}@g' "$audio_file"
  fi

  if [ -f "$output_file" ]; then
    if ! rg -q 'Ensure formatting always receives a valid numeric value\.' "$output_file" 2>/dev/null; then
      perl -0pi -e 's@local unit=\$\{2:-percent\}  # "percent" or "db"@local unit=\$\{2:-percent\}  # "percent" or "db"\n    # Ensure formatting always receives a valid numeric value.\n    if ! [[ "\$vol" =~ ^[0-9]+([.][0-9]+)?\$ ]]; then\n        vol="0"\n    fi@g' "$output_file"
    fi
  fi

  if [ -f "$volnoti_plugin" ] && ! rg -q 'Do not fall back to libnotify/notify-send when volnoti is selected\.' "$volnoti_plugin" 2>/dev/null; then
    perl -0pi -e 's@if is_muted; then "\$executable" -m "\$vol"\n    else "\$executable" "\$vol"; fi@if is_muted; then "\$executable" -m "\$vol" || true\n    else "\$executable" "\$vol" || true\n    fi\n    # Do not fall back to libnotify/notify-send when volnoti is selected.\n    return 0@' "$volnoti_plugin"
  fi

  if [ -f "$volnoti_plugin" ] && ! rg -q 'vol_int=' "$volnoti_plugin" 2>/dev/null; then
    perl -0pi -e 's@local vol=\$1 icon=\$2 summary=\$3 body=\$\{\*:4\}\n    local executable@local vol=\$1 icon=\$2 summary=\$3 body=\$\{\*:4\}\n    local vol_int\n    local executable@' "$volnoti_plugin"
    perl -0pi -e 's@command_exists "\$executable" \|\| \{ error "\$executable not found\. Please install it or set VOLNOTI_PATH to the correct path\."; exit "\$EX_UNAVAILABLE"; \}@command_exists "\$executable" || { error "\$executable not found. Please install it or set VOLNOTI_PATH to the correct path."; exit "$EX_UNAVAILABLE"; }\n    vol_int=\$(awk -v v="\${vol:-0}" '\''BEGIN { n = int(v + 0.5); if (n < 0) n = 0; if (n > 100) n = 100; print n }'\'')@' "$volnoti_plugin"
    perl -0pi -e 's@"\$executable" -m "\$vol"@"\$executable" -m "\$vol_int"@g; s@"\$executable" "\$vol"@"\$executable" "\$vol_int"@g' "$volnoti_plugin"
  fi

  if [ -f "$volnoti_plugin" ]; then
    cat >"$volnoti_plugin" <<'EOF'
#!/bin/bash
# Built-in volnoti notification plugin
notify_volume_volnoti() {
    # shellcheck disable=SC2034  # icon, summary, and body are part of the plugin interface but unused by volnoti
    local vol=$1 icon=$2 summary=$3 body=${*:4}
    local vol_int
    local executable="${VOLNOTI_PATH:+${VOLNOTI_PATH%/}/}volnoti-show"

    command_exists "$executable" || { error "$executable not found. Please install it or set VOLNOTI_PATH to the correct path."; exit "$EX_UNAVAILABLE"; }
    vol_int=$(awk -v v="${vol:-0}" 'BEGIN { n = int(v + 0.5); if (n < 0) n = 0; if (n > 100) n = 100; print n }')

    # volnoti-show requires the volnoti daemon; start it if needed.
    if ! pgrep -x volnoti >/dev/null 2>&1; then
        volnoti >/tmp/volnoti.log 2>&1 &
        sleep 0.05
    fi

    if is_muted; then "$executable" -m "$vol_int" || true
    else "$executable" "$vol_int" || true
    fi
    # Do not fall back to libnotify/notify-send when volnoti is selected.
    return 0
}
EOF
    chmod +x "$volnoti_plugin" 2>/dev/null || true
  fi
}

install_i3_volume() {
  local repo_root="$HOME/.config/i3/vendor/i3-volume"
  local bin_dir="$HOME/.local/bin"
  local config_dir="$HOME/.config/i3-volume"
  local config_file="$config_dir/config"

  if ! need_cmd git; then
    error "git is required to install i3-volume."
    return 1
  fi
  ensure_volnoti_available || return 1
  if ! pgrep -x volnoti >/dev/null 2>&1; then
    volnoti >/tmp/volnoti.log 2>&1 &
  fi

  if [ -d "$repo_root/.git" ]; then
    info "Updating i3-volume at $repo_root..."
    git -C "$repo_root" fetch --depth 1 origin "$I3_VOLUME_REPO_BRANCH" >/dev/null 2>&1 || {
      warn "Failed to fetch latest i3-volume updates; keeping current checkout."
    }
    git -C "$repo_root" checkout -q "$I3_VOLUME_REPO_BRANCH" >/dev/null 2>&1 || true
    git -C "$repo_root" pull --ff-only >/dev/null 2>&1 || {
      warn "Could not fast-forward i3-volume checkout; keeping existing version."
    }
  else
    info "Cloning i3-volume into $repo_root..."
    mkdir -p "$(dirname "$repo_root")"
    backup_path_if_exists "$repo_root" "i3-volume checkout"
    rm -rf "$repo_root"
    if ! git clone --depth 1 --branch "$I3_VOLUME_REPO_BRANCH" "$I3_VOLUME_REPO_URL" "$repo_root" >/dev/null 2>&1; then
      error "Failed to clone i3-volume from $I3_VOLUME_REPO_URL"
      return 1
    fi
  fi

  apply_i3_volume_compat_patches "$repo_root"

  mkdir -p "$bin_dir"
  ln -sfn "$repo_root/volume" "$bin_dir/volume"
  chmod +x "$repo_root/volume" >/dev/null 2>&1 || true
  success "Installed i3-volume command at $bin_dir/volume"

  mkdir -p "$config_dir"
  if [ ! -f "$config_file" ]; then
    cat > "$config_file" <<'EOF'
NOTIFICATION_METHOD="volnoti"
DISPLAY_NOTIFICATIONS=true
DEFAULT_STEP=5
MAX_VOL=100
EOF
    success "Created default i3-volume config at $config_file"
  else
    if rg -q '^[[:space:]]*NOTIFICATION_METHOD=' "$config_file" 2>/dev/null; then
      sed -i 's/^[[:space:]]*NOTIFICATION_METHOD=.*/NOTIFICATION_METHOD="volnoti"/' "$config_file"
    else
      printf '\nNOTIFICATION_METHOD="volnoti"\n' >> "$config_file"
    fi

    if rg -q '^[[:space:]]*DISPLAY_NOTIFICATIONS=' "$config_file" 2>/dev/null; then
      sed -i 's/^[[:space:]]*DISPLAY_NOTIFICATIONS=.*/DISPLAY_NOTIFICATIONS=true/' "$config_file"
    else
      printf 'DISPLAY_NOTIFICATIONS=true\n' >> "$config_file"
    fi
    success "Updated i3-volume config to use volnoti"
  fi
}

install_printer_plugin_packages_debian() {
  run_privileged_cmd \
    "Updating apt metadata for printer plugin dependencies." \
    apt-get update -qq
  run_privileged_cmd \
    "Installing printer plugin dependencies (CUPS + pycups runtime/build headers)." \
    apt-get install -y git cups python3-cups libcups2-dev build-essential pkg-config python3-dev
}

install_printer_plugin_packages_arch() {
  run_privileged_cmd \
    "Installing printer plugin dependencies (CUPS + pycups runtime)." \
    pacman -S --needed --noconfirm git cups python-pycups base-devel pkgconf python
}

sync_printer_plugin_repo() {
  local target_root="$HOME/.config/i3/hanauta/plugins"
  local target_dir="$target_root/$PRINTER_PLUGIN_ID"
  local origin_url=""

  mkdir -p "$target_root"

  if [ -d "$target_dir/.git" ]; then
    origin_url="$(git -C "$target_dir" remote get-url origin 2>/dev/null || true)"
    if [ "$origin_url" = "$PRINTER_PLUGIN_REPO_URL" ]; then
      info "Updating printer plugin at $target_dir..."
      git -C "$target_dir" fetch --depth 1 origin "$PRINTER_PLUGIN_REPO_BRANCH" >/dev/null 2>&1 || {
        warn "Failed to fetch latest printer plugin changes."
      }
      git -C "$target_dir" checkout -q "$PRINTER_PLUGIN_REPO_BRANCH" >/dev/null 2>&1 || true
      git -C "$target_dir" pull --ff-only >/dev/null 2>&1 || {
        warn "Could not fast-forward printer plugin checkout; keeping existing revision."
      }
    else
      if [ "$INSTALL_UPDATE_MODE" = true ]; then
        warn "Existing $target_dir has a different git origin. Updater mode will preserve it and skip replacement."
        return 0
      fi
      warn "Existing $target_dir is a git repo with a different origin. Replacing it."
      backup_path_if_exists "$target_dir" "printer plugin checkout"
      rm -rf "$target_dir"
    fi
  fi

  if [ ! -d "$target_dir/.git" ]; then
    info "Cloning printer plugin into $target_dir..."
    backup_path_if_exists "$target_dir" "printer plugin checkout"
    rm -rf "$target_dir"
    if ! git clone --depth 1 --branch "$PRINTER_PLUGIN_REPO_BRANCH" "$PRINTER_PLUGIN_REPO_URL" "$target_dir" >/dev/null 2>&1; then
      error "Failed to clone printer plugin from $PRINTER_PLUGIN_REPO_URL"
      return 1
    fi
  fi

  if [ -d "$target_dir/bin" ]; then
    find "$target_dir/bin" -type f -name '*.sh' -exec chmod +x {} \; 2>/dev/null || true
  fi

  success "Printer plugin is installed and updated at $target_dir"
}

install_printer_plugin_only() {
  if ! need_cmd git; then
    error "git is required to install the printer plugin."
    return 1
  fi

  if detect_debian_like; then
    info "Detected Debian-based distribution"
    install_printer_plugin_packages_debian || return 1
  elif detect_arch; then
    info "Detected Arch Linux distribution"
    install_printer_plugin_packages_arch || return 1
  else
    warn "Unknown distro; skipping package auto-install."
    warn "Install dependencies manually: CUPS + pycups."
  fi

  sync_printer_plugin_repo || return 1

  info "Printer plugin install/update complete."
  return 0
}

offer_mail_desktop_setup() {
  local helper="$HOME/.config/i3/hanauta/scripts/install_mail_desktop.sh"
  local desktop_id="hanauta-mail.desktop"
  local target_desktop="$HOME/.local/share/applications/$desktop_id"
  local -a args=()

  if [ -f "$target_desktop" ]; then
    info "Hanauta Mail desktop integration is already installed; skipping optional mail integration prompt."
    return 0
  fi

  echo ""
  echo -e "${MAGENTA}${BOLD}Optional Hanauta Mail Desktop Integration${NC}"
  echo -e "Install a desktop entry for ${BOLD}Hanauta Mail${NC} so it appears in app launchers and can be selected by desktop tools."
  if ! confirm_yes "Do you want to install Hanauta Mail desktop integration?"; then
    info "Skipping Hanauta Mail desktop integration."
    return 0
  fi

  if [ ! -f "$helper" ]; then
    warn "Mail desktop integration helper not found at $helper"
    return 1
  fi

  if confirm_yes "Do you want Hanauta Mail to support mailto links?"; then
    args+=(--mailto)
  fi

  info "Installing Hanauta Mail desktop integration..."
  if bash "$helper" "${args[@]}"; then
    success "Hanauta Mail desktop integration installed"
  else
    warn "Hanauta Mail desktop integration could not be completed"
  fi
}


disable_conflicting_notification_autostarts() {
  local autostart_dir="$HOME/.config/autostart"
  local override_file="$autostart_dir/xfce4-notifyd.desktop"
  local dbus_service_dir="$HOME/.local/share/dbus-1/services"
  local dbus_service_file="$dbus_service_dir/org.freedesktop.Notifications.service"
  local hanauta_notifyd="$HOME/.config/i3/hanauta/bin/hanauta-notifyd"

  mkdir -p "$autostart_dir"
  cat >"$override_file" <<'EOF'
[Desktop Entry]
Type=Application
Name=XFCE Notification Daemon
Hidden=true
EOF
  success "Disabled xfce4-notifyd XDG autostart override at $override_file"

  mkdir -p "$dbus_service_dir"
  cat >"$dbus_service_file" <<EOF
[D-BUS Service]
Name=org.freedesktop.Notifications
Exec=$hanauta_notifyd
EOF
  success "Configured Hanauta as the user DBus notification service at $dbus_service_file"

  pkill -x xfce4-notifyd 2>/dev/null || true
  pkill -x notification-daemon 2>/dev/null || true
  pkill -x mate-notification-daemon 2>/dev/null || true
  pkill -x dunst 2>/dev/null || true
  pkill -x deadd-notification-center 2>/dev/null || true
  if command -v systemctl >/dev/null 2>&1; then
    systemctl --user stop xfce4-notifyd.service 2>/dev/null || true
    systemctl --user disable xfce4-notifyd.service 2>/dev/null || true
    systemctl --user mask xfce4-notifyd.service 2>/dev/null || true
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
    install_selected_theme_to_root "$theme" "$destination_root" || true
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

build_sweet_cursor_theme() {
  local repo_root="$1"
  local cursor_root="$repo_root/kde/cursors"

  if [ ! -d "$cursor_root" ]; then
    return 1
  fi

  if [ -d "$cursor_root/Sweet-cursors" ] || [ -d "$cursor_root/sweet-cursors" ] || [ -d "$cursor_root/Sweet_Cursors" ]; then
    return 0
  fi

  if ! need_cmd inkscape || ! need_cmd xcursorgen; then
    warn "Cannot build $SWEET_CURSOR_THEME_NAME: missing inkscape and/or xcursorgen."
    return 1
  fi

  info "Building $SWEET_CURSOR_THEME_NAME from source..."
  local attempt=1
  local max_attempts=3
  while [ "$attempt" -le "$max_attempts" ]; do
    if (cd "$cursor_root" && run_cmd_silencing_inkscape_stderr bash build.sh); then
      break
    fi
    if [ "$attempt" -lt "$max_attempts" ]; then
      warn "Cursor build attempt ${attempt}/${max_attempts} failed; retrying..."
      sleep 1
    else
      warn "Failed to build $SWEET_CURSOR_THEME_NAME with build.sh after ${max_attempts} attempts."
      return 1
    fi
    attempt=$((attempt + 1))
  done

  [ -d "$cursor_root/Sweet-cursors" ] || [ -d "$cursor_root/sweet-cursors" ] || [ -d "$cursor_root/Sweet_Cursors" ]
}

install_sweet_cursor_theme_files() {
  local destination_root="$1"
  local tmp_root=""
  local repo_root=""
  local source_dir=""
  local destination_dir="$destination_root/$SWEET_CURSOR_THEME_NAME"

  mkdir -p "$destination_root"
  if [ -d "$destination_dir/cursors" ] && [ -f "$destination_dir/index.theme" ]; then
    info "$SWEET_CURSOR_THEME_NAME is already installed at $destination_dir; skipping rebuild."
    return 0
  fi

  tmp_root="$(mktemp -d)"
  repo_root="$tmp_root/sweet-repo"

  if ! git clone --depth 1 --branch "$SWEET_CURSOR_REPO_BRANCH" "$SWEET_CURSOR_REPO_URL" "$repo_root" >/dev/null 2>&1; then
    warn "Could not clone $SWEET_CURSOR_REPO_URL ($SWEET_CURSOR_REPO_BRANCH)."
    rm -rf "$tmp_root"
    return 1
  fi

  build_sweet_cursor_theme "$repo_root" || {
    rm -rf "$tmp_root"
    return 1
  }

  for candidate in \
    "$repo_root/kde/cursors/Sweet-cursors" \
    "$repo_root/kde/cursors/sweet-cursors" \
    "$repo_root/kde/cursors/Sweet_Cursors"; do
    if [ -d "$candidate" ]; then
      source_dir="$candidate"
      break
    fi
  done

  if [ -z "$source_dir" ]; then
    warn "Built cursor theme directory was not found in upstream sources."
    rm -rf "$tmp_root"
    return 1
  fi

  rm -rf "$destination_dir"
  copy_theme_tree "$source_dir" "$destination_dir"
  rm -rf "$tmp_root"
  success "$SWEET_CURSOR_THEME_NAME installed to $destination_dir"
}

apply_cursor_theme_defaults() {
  local icons_default_dir="$HOME/.icons/default"
  local index_file="$icons_default_dir/index.theme"

  mkdir -p "$icons_default_dir"
  cat > "$index_file" <<EOF
[Icon Theme]
Inherits=$SWEET_CURSOR_THEME_NAME
EOF

  if need_cmd gsettings; then
    gsettings set org.gnome.desktop.interface cursor-theme "$SWEET_CURSOR_THEME_NAME" >/dev/null 2>&1 || true
    gsettings set org.gnome.desktop.interface cursor-size "$SWEET_CURSOR_THEME_SIZE" >/dev/null 2>&1 || true
  fi

  xrdb -merge <<EOF >/dev/null 2>&1 || true
Xcursor.theme: $SWEET_CURSOR_THEME_NAME
Xcursor.size: $SWEET_CURSOR_THEME_SIZE
EOF
  success "Cursor defaults set to $SWEET_CURSOR_THEME_NAME ($SWEET_CURSOR_THEME_SIZE)"
}

install_sweet_cursor_theme() {
  info "Installing $SWEET_CURSOR_THEME_NAME..."
  local user_theme_dir="$HOME/.icons/$SWEET_CURSOR_THEME_NAME"
  if ! install_sweet_cursor_theme_files "$HOME/.icons"; then
    warn "$SWEET_CURSOR_THEME_NAME could not be installed. Keeping existing cursor settings."
    return 1
  fi

  apply_cursor_theme_defaults

  if [ "$INSTALL_CURSOR_THEME_TO_SYSTEM" = true ]; then
    if ! need_cmd sudo; then
      warn "sudo not found; skipping system-wide cursor install to /usr/share/icons."
      return 0
    fi
    if [ ! -d "$user_theme_dir" ]; then
      warn "User cursor theme directory missing: $user_theme_dir"
      return 0
    fi
    info "Installing $SWEET_CURSOR_THEME_NAME system-wide to /usr/share/icons with sudo..."
    sudo mkdir -p /usr/share/icons
    sudo rm -rf "/usr/share/icons/$SWEET_CURSOR_THEME_NAME"
    sudo cp -a "$user_theme_dir" "/usr/share/icons/"
    success "$SWEET_CURSOR_THEME_NAME installed system-wide at /usr/share/icons/$SWEET_CURSOR_THEME_NAME"
  fi
}

download_adw_gtk_release_archive() {
  local output_file="$1"
  local api_url="https://api.github.com/repos/$ADW_GTK_REPO/releases/latest"
  local asset_url=""

  if ! need_cmd jq; then
    warn "jq is required to resolve adw-gtk3 release assets."
    return 1
  fi

  asset_url="$(curl -fsSL "$api_url" | jq -r '.assets[]?.browser_download_url | select(test("adw-gtk3v[0-9].*\\.tar\\.xz$"))' | head -n 1)"
  if [ -z "$asset_url" ] || [ "$asset_url" = "null" ]; then
    warn "Could not find adw-gtk3 release archive URL."
    return 1
  fi

  curl -fsSL -o "$output_file" "$asset_url"
}

install_adw_gtk_theme_files() {
  local destination_root="$1"
  local temp_root=""
  local archive_file=""
  local unpack_root=""
  local candidate_root=""

  mkdir -p "$destination_root"
  temp_root="$(mktemp -d)"
  archive_file="$temp_root/adw-gtk3.tar.xz"
  unpack_root="$temp_root/unpack"

  if ! download_adw_gtk_release_archive "$archive_file"; then
    rm -rf "$temp_root"
    return 1
  fi

  mkdir -p "$unpack_root"
  tar -xJf "$archive_file" -C "$unpack_root"

  if [ -d "$unpack_root/adw-gtk3" ] && [ -d "$unpack_root/adw-gtk3-dark" ]; then
    candidate_root="$unpack_root"
  else
    for candidate in "$unpack_root"/*; do
      if [ -d "$candidate/adw-gtk3" ] && [ -d "$candidate/adw-gtk3-dark" ]; then
        candidate_root="$candidate"
        break
      fi
    done
  fi

  if [ -z "$candidate_root" ]; then
    warn "Could not locate adw-gtk3 theme folders in release archive."
    rm -rf "$temp_root"
    return 1
  fi

  copy_theme_tree "$candidate_root/adw-gtk3" "$destination_root/adw-gtk3"
  copy_theme_tree "$candidate_root/adw-gtk3-dark" "$destination_root/adw-gtk3-dark"
  rm -rf "$temp_root"
  success "Installed adw-gtk3 and adw-gtk3-dark to $destination_root"
}

apply_gtk_theme_defaults() {
  local selected_theme="$1"
  local color_scheme="default"

  if [ "$selected_theme" = "adw-gtk3-dark" ]; then
    color_scheme="prefer-dark"
  fi

  if need_cmd gsettings; then
    gsettings set org.gnome.desktop.interface gtk-theme "$selected_theme" >/dev/null 2>&1 || true
    gsettings set org.gnome.desktop.interface color-scheme "$color_scheme" >/dev/null 2>&1 || true
  fi
  success "GTK theme set to $selected_theme (color-scheme: $color_scheme)"
}

install_adw_gtk_theme() {
  local selected_theme="$1"
  info "Installing GTK theme: $selected_theme..."
  if install_adw_gtk_theme_files "$HOME/.themes"; then
    apply_gtk_theme_defaults "$selected_theme"
  else
    warn "Failed to install adw-gtk3 themes."
    return 1
  fi
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
  echo -e "  ${GREEN}✓${NC} Rubik fonts"
  echo -e "  ${GREEN}✓${NC} Sweet cursor theme"
  echo -e "  ${GREEN}✓${NC} i3-volume + volnoti"
  echo -e "  ${GREEN}✓${NC} Optional custom themes"
  echo ""
}

post_notes() {
  echo ""
  echo -e "${YELLOW}Important notes:${NC}"
  echo -e "  • Ensure ${BOLD}~/.local/bin${NC} is on PATH so bundled binaries like ${BOLD}matugen${NC} and ${BOLD}hellwal${NC} are usable"
  echo -e "  • GTK themes are written for both ${BOLD}gtk-3.0${NC} and ${BOLD}gtk-4.0${NC} when applied from Hanauta Settings"
  echo -e "  • Cursor defaults are set to ${BOLD}${SWEET_CURSOR_THEME_NAME}${NC} (${BOLD}${SWEET_CURSOR_THEME_SIZE}${NC}) to match Caelestia"
  echo -e "  • Volume keys are wired through ${BOLD}i3-volume${NC} with ${BOLD}volnoti${NC} notifications"
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
  init_safety_backups
  if [ "$INSTALL_UPDATE_MODE" = true ]; then
    info "Updater mode enabled: preserve local state and avoid destructive replacements where possible."
    info "Safety backups root: $SAFETY_BACKUP_ROOT"
  fi

  if [ "$INSTALL_PRINTER_PLUGIN_ONLY" = true ] && \
     { [ "$INSTALL_GTK_THEME_ONLY" = true ] || \
       [ "$INSTALL_CURSOR_ONLY" = true ] || \
       [ "$INSTALL_RUBIK_FONT_ONLY" = true ] || \
       [ "$INSTALL_VSCODE_ONLY" = true ] || \
       [ "$INSTALL_VSCODIUM_ONLY" = true ] || \
       [ "$INSTALL_I3_VOLUME_ONLY" = true ] || \
       [ "$INSTALL_CUSTOM_THEMES" = true ] || \
       [ "$INSTALL_WIREGUARD_SYSTEMD_ONLY" = true ] || \
       [ "$INSTALL_NOTIFICATION_DAEMON_ONLY" = true ] || \
       [ "$INSTALL_QUICKSHELL_ONLY" = true ] || \
       [ "$INSTALL_SDDM_ONLY" = true ] || \
       [ "$INSTALL_HANAUTA_SERVICE_ONLY" = true ]; }; then
    error "--printer-plugin must be used by itself."
    return 1
  fi

  if [ "$INSTALL_SDDM_ONLY" = true ] && \
     { [ "$INSTALL_GTK_THEME_ONLY" = true ] || \
       [ "$INSTALL_CURSOR_ONLY" = true ] || \
       [ "$INSTALL_RUBIK_FONT_ONLY" = true ] || \
       [ "$INSTALL_VSCODE_ONLY" = true ] || \
       [ "$INSTALL_VSCODIUM_ONLY" = true ] || \
       [ "$INSTALL_I3_VOLUME_ONLY" = true ] || \
       [ "$INSTALL_CUSTOM_THEMES" = true ] || \
       [ "$INSTALL_WIREGUARD_SYSTEMD_ONLY" = true ] || \
       [ "$INSTALL_NOTIFICATION_DAEMON_ONLY" = true ] || \
       [ "$INSTALL_QUICKSHELL_ONLY" = true ] || \
       [ "$INSTALL_HANAUTA_SERVICE_ONLY" = true ]; }; then
    error "--sddm must be used by itself."
    return 1
  fi

  if [ "$INSTALL_I3_VOLUME_ONLY" = true ] && \
     { [ "$INSTALL_GTK_THEME_ONLY" = true ] || \
       [ "$INSTALL_CURSOR_ONLY" = true ] || \
       [ "$INSTALL_RUBIK_FONT_ONLY" = true ] || \
       [ "$INSTALL_VSCODE_ONLY" = true ] || \
       [ "$INSTALL_VSCODIUM_ONLY" = true ] || \
       [ "$INSTALL_CUSTOM_THEMES" = true ] || \
       [ "$INSTALL_WIREGUARD_SYSTEMD_ONLY" = true ] || \
       [ "$INSTALL_NOTIFICATION_DAEMON_ONLY" = true ] || \
       [ "$INSTALL_QUICKSHELL_ONLY" = true ] || \
       [ "$INSTALL_SDDM_ONLY" = true ] || \
       [ "$INSTALL_HANAUTA_SERVICE_ONLY" = true ]; }; then
    error "--i3-volume must be used by itself."
    return 1
  fi

  local shell_only_count=0
  if [ "$INSTALL_BLESH_ONLY" = true ]; then
    shell_only_count=$((shell_only_count + 1))
  fi
  if [ "$INSTALL_ZSH_THEME_ONLY" = true ]; then
    shell_only_count=$((shell_only_count + 1))
  fi
  if [ "$INSTALL_FISH_THEME_ONLY" = true ]; then
    shell_only_count=$((shell_only_count + 1))
  fi
  if [ "$shell_only_count" -gt 1 ]; then
    error "Use only one of --blesh, --zsh, or --fish."
    return 1
  fi

  if [ "$shell_only_count" -eq 1 ] && \
     { [ "$INSTALL_GTK_THEME_ONLY" = true ] || \
       [ "$INSTALL_CURSOR_ONLY" = true ] || \
       [ "$INSTALL_RUBIK_FONT_ONLY" = true ] || \
       [ "$INSTALL_VSCODE_ONLY" = true ] || \
       [ "$INSTALL_VSCODIUM_ONLY" = true ] || \
       [ "$INSTALL_I3_VOLUME_ONLY" = true ] || \
       [ "$INSTALL_CUSTOM_THEMES" = true ] || \
       [ "$INSTALL_WIREGUARD_SYSTEMD_ONLY" = true ] || \
       [ "$INSTALL_NOTIFICATION_DAEMON_ONLY" = true ] || \
       [ "$INSTALL_QUICKSHELL_ONLY" = true ] || \
       [ "$INSTALL_SDDM_ONLY" = true ] || \
       [ "$INSTALL_PRINTER_PLUGIN_ONLY" = true ] || \
       [ "$INSTALL_HANAUTA_SERVICE_ONLY" = true ]; }; then
    error "--blesh, --zsh, and --fish must be used by themselves."
    return 1
  fi

  if [ "$INSTALL_PRINTER_PLUGIN_ONLY" = true ]; then
    print_banner
    install_printer_plugin_only
    info "Done!"
    return 0
  fi

  if [ "$INSTALL_HANAUTA_SERVICE_ONLY" = true ]; then
    print_banner
    copy_dotfiles
    build_native_services
    install_hanauta_service_root
    info "Done!"
    return 0
  fi

  if [ "$INSTALL_SDDM_ONLY" = true ]; then
    print_banner
    install_silent_sddm
    info "Done!"
    return 0
  fi

  if [ "$INSTALL_GTK_THEME_ONLY" = true ]; then
    GTK_THEME_SELECTION="$(normalize_gtk_theme_selection "$GTK_THEME_SELECTION")" || {
      error "Unsupported GTK theme selection: $GTK_THEME_SELECTION"
      return 1
    }
    print_banner
    install_adw_gtk_theme "$GTK_THEME_SELECTION"
    info "Done!"
    return 0
  fi

  if [ "$INSTALL_CURSOR_ONLY" = true ]; then
    SWEET_CURSOR_THEME_NAME="$(normalize_cursor_theme_selection "$SWEET_CURSOR_THEME_NAME")" || {
      error "Unsupported cursor theme selection: $SWEET_CURSOR_THEME_NAME"
      return 1
    }
    print_banner
    install_sweet_cursor_theme
    info "Done!"
    return 0
  fi

  if [ "$INSTALL_RUBIK_FONT_ONLY" = true ]; then
    print_banner
    install_rubik_fonts
    info "Done!"
    return 0
  fi

  if [ "$INSTALL_BLESH_ONLY" = true ]; then
    print_banner
    ensure_shell_theme_dependency blesh && install_bash_theme_blesh
    info "Done!"
    return 0
  fi

  if [ "$INSTALL_ZSH_THEME_ONLY" = true ]; then
    print_banner
    ensure_shell_theme_dependency zsh && install_zsh_theme
    info "Done!"
    return 0
  fi

  if [ "$INSTALL_FISH_THEME_ONLY" = true ]; then
    print_banner
    ensure_shell_theme_dependency fish && install_fish_theme
    info "Done!"
    return 0
  fi

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

  if [ "$INSTALL_I3_VOLUME_ONLY" = true ]; then
    print_banner
    if detect_debian_like; then
      echo -e "${CYAN}[*]${NC} Updating package lists..."
      sudo apt-get update -qq
      install_apt_group "i3-volume prerequisites" bc
    elif detect_arch; then
      install_pacman_group "i3-volume prerequisites" bc
    else
      warn "Unknown distro; skipping package install for i3-volume prerequisites."
    fi
    install_i3_volume
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

  copy_dotfiles
  link_configs
  make_exec
  install_local_binaries
  install_rubik_fonts

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
  build_native_services
  install_hanauta_service_root
  ensure_dock_defaults
  ensure_hanauta_settings
  disable_conflicting_notification_autostarts
  install_sweet_cursor_theme
  if [ "$INSTALL_NOTIFICATION_DAEMON_ONLY" = false ] && [ "$INSTALL_QUICKSHELL_ONLY" = false ]; then
    ensure_betterlockscreen_available
  fi
  if [ "$INSTALL_NOTIFICATION_DAEMON_ONLY" = false ] && [ "$INSTALL_QUICKSHELL_ONLY" = false ]; then
    install_i3_volume
  fi
  if [ "$INSTALL_NOTIFICATION_DAEMON_ONLY" = false ] && [ "$INSTALL_QUICKSHELL_ONLY" = false ] && [ "$INSTALL_EDITOR_EXTENSIONS_AUTO" = true ]; then
    install_detected_editor_extensions
  fi
  if [ "$INSTALL_NOTIFICATION_DAEMON_ONLY" = false ] && [ "$INSTALL_QUICKSHELL_ONLY" = false ]; then
    offer_mail_desktop_setup
    offer_shell_theme_customization
    offer_custom_theme_install
    offer_silent_sddm_install
  fi

  offer_wireguard_systemd_setup

  print_summary
  post_notes

  info "Done!"
}

main "$@"
