from __future__ import annotations

from pathlib import Path


PICOM_DEFAULT_TEMPLATE = """backend = "glx";
vsync = true;
use-damage = true;
detect-rounded-corners = true;
detect-client-opacity = true;
detect-transient = true;
mark-wmwin-focused = true;
mark-ovredir-focused = true;
log-level = "warn";

shadow = true;
shadow-radius = 18;
shadow-opacity = 0.18;
shadow-offset-x = -12;
shadow-offset-y = -12;
shadow-color = "#000000";

fading = false;
inactive-opacity = 1.0;
active-opacity = 1.0;
inactive-opacity-override = false;

corner-radius = 18;
transparent-clipping = false;
corner-radius-rules = [
  "88:name = 'PyQt Notification Center'"
];
{picom_rule_blocks}

wintypes:
{
  tooltip = {{ fade = false; shadow = false; focus = true; full-shadow = false; }};
  dock = {{ shadow = false; clip-shadow-above = true; }};
  dnd = {{ shadow = false; }};
  popup_menu = {{ shadow = false; }};
  dropdown_menu = {{ shadow = false; }};
};
"""


def picom_rule_file_defaults(
    shadow_exclude_file: Path,
    rounded_exclude_file: Path,
    opacity_rules_file: Path,
    fade_exclude_file: Path,
) -> dict[Path, str]:
    return {
        shadow_exclude_file: """# Hanauta picom shadow exceptions
# One rule per line. Supported shortcuts:
#   window_name: Exact Window Title
#   window_name_contains: Partial Title
#   class: WM_CLASS
#   window_type: dock
#   raw: any-valid-picom-condition

raw: bounding_shaped && !rounded_corners
class: Eww
window_type: dock
window_type: notification
window_type: utility
class: Rofi
class: Conky
window_name: Hanauta Launcher
window_name: Hanauta Window Switcher
window_name: Hanauta Hotkeys
window_name: Hanauta Weather
window_name: Hanauta Calendar
window_name: Hanauta Game Mode
window_name: Hanauta CAP Alerts
window_name: Hanauta CAP Alert
window_name: Hanauta Reminders
window_name: Hanauta Reminder
window_name: Hanauta Pomodoro
window_name: Hanauta OBS
window_name: Hanauta Crypto
window_name: Hanauta VPS
window_name: Hanauta Updates
window_name: Hanauta AI
window_name: WireGuard
window_name: Wi-Fi Control
window_name: ntfy Publisher
window_name: Christian Devotion
class: HanautaNotification
window_name_contains: Hanauta Notification
window_name: Hanauta Desktop Clock
window_name: Hanauta Settings
""",
        rounded_exclude_file: """# Hanauta picom rounded-corner exceptions
# Same shortcuts as shadow-exclude.rules.

window_type: dock
window_type: notification
window_type: utility
class: Rofi
class: Conky
class: mpv
window_name: PyQt Notification Center
class: HanautaNotification
window_name_contains: Hanauta Notification
window_name: Hanauta Desktop Clock
window_name: Hanauta Settings
""",
        opacity_rules_file: """# Hanauta picom opacity rules
# Syntax:
#   opacity 100: window_name: Exact Window Title
#   opacity 100: class: kitty
#   opacity 100: raw: focused

opacity 100: class: Eww
opacity 100: class: Alacritty
opacity 100: class: kitty
opacity 100: window_name: PyQt Notification Center
opacity 100: window_name: Hanauta Settings
""",
        fade_exclude_file: """# Hanauta picom fade exceptions
# Same shortcuts as shadow-exclude.rules.

window_name: Hanauta Launcher
window_name: Hanauta Settings
""",
    }

