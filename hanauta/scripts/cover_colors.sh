#!/usr/bin/env bash

cover_path="/tmp/cover.png"
default_colors="#1e1e2e #313244 #45475a #585b70 #6c6f85 #7f84a8 #89b4fa #cba6f7 #f5c2e7 #f38ba8 #fab387 #f9e2af #a6e3a1 #94e2d5 #74c7ec"

get_colors() {
    if [ ! -f "$cover_path" ]; then
        echo "$default_colors"
        return
    fi

    if [ -x "$HOME/.local/bin/hellwal" ]; then
        colors_json=$("$HOME/.local/bin/hellwal" -i "$cover_path" --json --quiet --no-cache --skip-term-colors 2>/dev/null)
        
        if [ -n "$colors_json" ]; then
            colors=""
            for i in $(seq 0 14); do
                c=$(echo "$colors_json" | grep -oP "\"color$i\":\s*\"\K[^\"]+" | head -1)
                if [ -n "$c" ]; then
                    colors="$colors$c "
                fi
            done
            
            if [ -n "$colors" ]; then
                echo "$colors" | sed 's/ $//'
                return
            fi
        fi
    fi
    
    echo "$default_colors"
}

case "$1" in
    colors) get_colors ;;
    *) get_colors ;;
esac
