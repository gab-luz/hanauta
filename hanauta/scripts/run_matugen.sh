#!/usr/bin/env bash

MATUGEN="$HOME/.config/i3/bin/matugen"
WALLPAPER="$1"
PYQT_THEME_DIR="$HOME/.local/state/hanauta/theme"
PYQT_THEME_FILE="$PYQT_THEME_DIR/pyqt_palette.json"
SETTINGS_FILE="$HOME/.local/state/hanauta/notification-center/settings.json"

matugen_notifications_enabled() {
  python3 - "$SETTINGS_FILE" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1]).expanduser()
enabled = True
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    payload = {}
appearance = payload.get("appearance", {}) if isinstance(payload, dict) else {}
if isinstance(appearance, dict):
    enabled = bool(appearance.get("matugen_notifications_enabled", True))
print("1" if enabled else "0")
PY
}

notify_matugen() {
  if [ "$(matugen_notifications_enabled)" = "1" ]; then
    notify-send "$1" "$2"
  fi
}

if [ -z "$WALLPAPER" ]; then
  WALLPAPER="$HOME/.wallpapers/tokyo.png"
fi

if [ ! -x "$MATUGEN" ]; then
  notify_matugen "Matugen" "Matugen not found at ~/.config/i3/bin/matugen"
  exit 1
fi

if [ ! -f "$WALLPAPER" ]; then
  notify_matugen "Matugen" "Wallpaper not found: $WALLPAPER"
  exit 1
fi

JSON=$($MATUGEN image "$WALLPAPER" --mode dark --json hex 2>/dev/null)

if [ -z "$JSON" ]; then
  SOURCE_COLOR="$(python3 - "$WALLPAPER" <<'PY'
import sys
from pathlib import Path

try:
    from PIL import Image
except Exception:
    print("")
    raise SystemExit(0)

path = Path(sys.argv[1]).expanduser()
try:
    image = Image.open(path).convert("RGB")
except Exception:
    print("")
    raise SystemExit(0)

# Downsample, quantize, then prefer a vivid non-extreme color instead of a flat mean.
thumb = image.resize((96, 96))
palette = thumb.quantize(colors=12, method=Image.Quantize.MEDIANCUT).convert("RGB")
counts = palette.getcolors(maxcolors=96 * 96) or []

def score(item):
    count, color = item
    r, g, b = color
    brightness = (r * 299 + g * 587 + b * 114) / 1000
    spread = max(color) - min(color)
    vivid = spread / 255.0
    brightness_penalty = abs(brightness - 132) / 132
    return (vivid * 3.0) + (count / (96 * 96)) - (brightness_penalty * 0.7)

if not counts:
    print("")
    raise SystemExit(0)

best = max(counts, key=score)[1]
print("#{0:02X}{1:02X}{2:02X}".format(*best))
PY
)"

  if [ -n "$SOURCE_COLOR" ]; then
    JSON=$($MATUGEN color hex "$SOURCE_COLOR" --mode dark --json hex 2>/dev/null)
  fi
fi

if [ -z "$JSON" ]; then
  notify_matugen "Matugen" "Failed to generate colors"
  exit 1
fi

export MATUGEN_JSON="$JSON"
export PYQT_THEME_DIR
export PYQT_THEME_FILE

eval "$(
python3 - <<'PY'
import json
import os
import shlex
from pathlib import Path

payload = json.loads(os.environ["MATUGEN_JSON"])
colors = payload.get("colors", {})

def pick(name: str, fallback: str) -> str:
    entry = colors.get(name, {})
    default = entry.get("default", {})
    value = str(default.get("color", fallback)).strip()
    return value if value.startswith("#") and len(value) == 7 else fallback

values = {
    "SOURCE": pick("source_color", "#D0BCFF"),
    "BG": pick("background", "#141218"),
    "FG": pick("on_background", "#E6E0E9"),
    "ACCENT": pick("primary", "#D0BCFF"),
    "ACCENT_DARK": pick("primary_container", "#4F378B"),
    "ON_ACCENT_DARK": pick("on_primary_container", "#EADDFF"),
    "SECONDARY": pick("secondary", "#CCC2DC"),
    "ON_SECONDARY": pick("on_secondary", "#332D41"),
    "TERTIARY": pick("tertiary", "#EFB8C8"),
    "ON_TERTIARY": pick("on_tertiary", "#492532"),
    "SURFACE": pick("surface", "#141218"),
    "ON_SURFACE": pick("on_surface", "#E6E0E9"),
    "SURFACE_CONTAINER": pick("surface_container", "#211F26"),
    "SURFACE_CONTAINER_HIGH": pick("surface_container_high", "#2B2930"),
    "SURFACE_VARIANT": pick("surface_variant", "#49454F"),
    "ON_SURFACE_VARIANT": pick("on_surface_variant", "#CAC4D0"),
    "OUTLINE": pick("outline", "#938F99"),
    "ERROR": pick("error", "#F2B8B5"),
    "ON_ERROR": pick("on_error", "#601410"),
}

Path(os.environ["PYQT_THEME_DIR"]).mkdir(parents=True, exist_ok=True)
Path(os.environ["PYQT_THEME_FILE"]).write_text(
    json.dumps(
        {
            "use_matugen": True,
            "source": values["SOURCE"],
            "primary": values["ACCENT"],
            "on_primary": pick("on_primary", "#381E72"),
            "primary_container": values["ACCENT_DARK"],
            "on_primary_container": values["ON_ACCENT_DARK"],
            "secondary": values["SECONDARY"],
            "on_secondary": values["ON_SECONDARY"],
            "tertiary": values["TERTIARY"],
            "on_tertiary": values["ON_TERTIARY"],
            "background": values["BG"],
            "on_background": values["FG"],
            "surface": values["SURFACE"],
            "on_surface": values["ON_SURFACE"],
            "surface_container": values["SURFACE_CONTAINER"],
            "surface_container_high": values["SURFACE_CONTAINER_HIGH"],
            "surface_variant": values["SURFACE_VARIANT"],
            "on_surface_variant": values["ON_SURFACE_VARIANT"],
            "outline": values["OUTLINE"],
            "error": values["ERROR"],
            "on_error": values["ON_ERROR"],
        },
        indent=2,
    ),
    encoding="utf-8",
)

for key, value in values.items():
    print(f"{key}={shlex.quote(value)}")
PY
)"

COLORS_FILE="$HOME/.config/i3/hanauta/src/eww/colors.scss"

cat > "$COLORS_FILE" << EOF
// Matugen Generated palette from $WALLPAPER
\$darkbg: #141218;
\$bg: $BG;
\$contrastbg: $SURFACE_VARIANT;
\$bgSecondary: $SURFACE;
\$bgSecondaryAlt: $SURFACE_VARIANT;
\$fg: $FG;
\$fgDim: $OUTLINE;

// Font families
\$font-icon: "Material Symbols Rounded";

// Aliases
\$background: \$bg;
\$backgroundSecondary: \$bgSecondary;
\$backgroundSecondaryAlt: \$bgSecondaryAlt;
\$foreground: \$fg;
\$foregroundDim: \$fgDim;

\$black: #161519;
\$dimblack: #1C1B1F;
\$lightblack: $SURFACE_VARIANT;
\$red: #FFB4AB;
\$blue: #A8C7FA;
\$cyan: #94F0F0;
\$blue-desaturated: $ACCENT;
\$magenta: $ACCENT;
\$purple: $ACCENT;
\$green: #C4EDD7;
\$aquamarine: #94F0F0;
\$yellow: #FFB784;
\$accent: $ACCENT;
\$javacafeMagenta: $ACCENT;
\$javacafeBlue: #A8C7FA;
\$putih: #FFFFFF;
\$orange: #FFB784;
\$kuning: #FFB784;
\$bluegray: $OUTLINE;
\$mussic: $SURFACE_VARIANT;
EOF

sassc -t expanded "$HOME/.config/i3/hanauta/src/eww/eww.scss.src" /tmp/eww.css && \
  sed '1{/^@charset/d;}' /tmp/eww.css > "$HOME/.config/i3/hanauta/src/eww/eww.css"

eww -c "$HOME/.config/i3/hanauta/src/eww" daemon --restart 2>/dev/null

notify_matugen "Matugen" "Applied colors from $(basename "$WALLPAPER")"
