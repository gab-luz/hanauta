#!/usr/bin/env bash

# Detect system color scheme preference (prefer-dark / prefer-light / default)
# Outputs: dark, light, or auto

GTK3_CONFIG="$HOME/.config/gtk-3.0/settings.ini"
GTK4_CONFIG="$HOME/.config/gtk-4.0/settings.ini"
GTK2_RC="$HOME/.gtkrc-2.0"

# Try gsettings first (most reliable for GNOME)
if command -v gsettings >/dev/null 2>&1; then
    value=$(gsettings get org.gnome.desktop.interface color-scheme 2>/dev/null || true)
    value=${value//\'/}
    case "$value" in
        prefer-dark) echo "dark"; exit 0 ;;
        prefer-light) echo "light"; exit 0 ;;
        default) ;;
    esac
fi

# Fallback: check GTK3 settings.ini
if [ -f "$GTK3_CONFIG" ]; then
    dark=$(awk -F= '/^gtk-application-prefer-dark-theme=/{print $2; exit}' "$GTK3_CONFIG" 2>/dev/null || true)
    if [ "$dark" = "1" ]; then
        echo "dark"
        exit 0
    elif [ "$dark" = "0" ]; then
        echo "light"
        exit 0
    fi
fi

# Fallback: check GTK4 settings.ini
if [ -f "$GTK4_CONFIG" ]; then
    dark=$(awk -F= '/^gtk-application-prefer-dark-theme=/{print $2; exit}' "$GTK4_CONFIG" 2>/dev/null || true)
    if [ "$dark" = "1" ]; then
        echo "dark"
        exit 0
    elif [ "$dark" = "0" ]; then
        echo "light"
        exit 0
    fi
fi

# Fallback: check GTK2 rc
if [ -f "$GTK2_RC" ]; then
    dark=$(awk -F= '/^gtk-application-prefer-dark-theme=/{print $2; exit}' "$GTK2_RC" 2>/dev/null | tr -d '"' || true)
    if [ "$dark" = "1" ]; then
        echo "dark"
        exit 0
    elif [ "$dark" = "0" ]; then
        echo "light"
        exit 0
    fi
fi

# Default to dark if nothing found
echo "dark"