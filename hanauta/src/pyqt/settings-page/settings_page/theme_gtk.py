import shutil
import subprocess
from pathlib import Path

from settings_page.theme_data import HANAUTA_FONT_PROFILE, THEME_LIBRARY, THEMES_HOME


def selected_theme_key(settings_state: dict) -> str:
    appearance = settings_state.get("appearance", {})
    from settings_page.theme_data import THEME_CHOICES, CUSTOM_THEME_KEYS
    choice = str(appearance.get("theme_choice", "dark")).strip().lower()
    if choice == "custom":
        custom_theme = (
            str(appearance.get("custom_theme_id", "retrowave")).strip().lower()
        )
        return custom_theme if custom_theme in CUSTOM_THEME_KEYS else "retrowave"
    if choice == "light":
        return "hanauta_light"
    return "hanauta_dark"


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _copytree_clean(source: Path, destination: Path) -> None:
    if destination.exists() or destination.is_symlink():
        shutil.rmtree(destination, ignore_errors=True)
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns(".git", ".github", "node_modules", "__pycache__"),
        dirs_exist_ok=False,
    )


def _blend_hex(a: str, b: str, t: float) -> str:
    ra, ga, ba = int(a[1:3], 16), int(a[3:5], 16), int(a[5:7], 16)
    rb, gb, bb = int(b[1:3], 16), int(b[3:5], 16), int(b[5:7], 16)
    r = int(ra + (rb - ra) * t)
    g = int(ga + (gb - ga) * t)
    b = int(ba + (bb - ba) * t)
    return f"#{r:02X}{g:02X}{b:02X}"


def _shade(color: str, factor: float) -> str:
    if factor >= 0:
        return _blend_hex(color, "#FFFFFF", factor)
    return _blend_hex(color, "#000000", -factor)


def _rgba_str(color: str, alpha: float) -> str:
    r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
    return f"rgba({r}, {g}, {b}, {alpha:.2f})"


def _hanauta_gtk_css(palette: dict[str, str],
                     font_family: str = "Rubik",
                     mono_font_family: str = "JetBrains Mono") -> str:
    bg = palette["background"]
    fg = palette["on_background"]
    base = palette["surface_container"]
    text = palette["on_surface"]
    selected_bg = palette["primary"]
    selected_fg = palette["on_primary"]
    border = palette["outline"]
    surface = palette["surface"]
    container_high = palette["surface_container_high"]
    variant = palette["surface_variant"]
    on_variant = palette["on_surface_variant"]
    error = palette["error"]
    on_error = palette["on_error"]
    primary_cont = palette["primary_container"]
    on_primary_cont = palette["on_primary_container"]
    secondary = palette["secondary"]
    on_secondary = palette["on_secondary"]
    tertiary = palette["tertiary"]
    on_tertiary = palette["on_tertiary"]

    base_hover = _shade(base, -0.05)
    base_active = _shade(base, -0.10)

    return (
        f"""
@define-color theme_bg_color {bg};
@define-color theme_fg_color {fg};
@define-color theme_base_color {base};
@define-color theme_text_color {text};
@define-color theme_selected_bg_color {selected_bg};
@define-color theme_selected_fg_color {selected_fg};
@define-color insensitive_bg_color {_rgba_str(bg, 0.50)};
@define-color insensitive_fg_color {_rgba_str(text, 0.45)};
@define-color insensitive_base_color {_rgba_str(base, 0.50)};
@define-color borders {border};
@define-color unfocused_borders {_rgba_str(border, 0.55)};
@define-color warning_color {_shade(secondary, 0.15)};
@define-color error_color {error};
@define-color success_color {selected_bg};
@define-color accent_color {selected_bg};
@define-color accent_bg_color {selected_bg};
@define-color accent_fg_color {selected_fg};
@define-color window_bg_color {bg};
@define-color window_fg_color {fg};
@define-color view_bg_color {base};
@define-color view_fg_color {text};
@define-color headerbar_bg_color {container_high};
@define-color headerbar_fg_color {text};
@define-color headerbar_border_color {border};
@define-color headerbar_backdrop_color {_shade(container_high, -0.03)};
@define-color titlebar_bg_color {container_high};
@define-color titlebar_fg_color {text};
@define-color menubar_bg_color {container_high};
@define-color menubar_fg_color {text};
@define-color toolbar_bg_color {_rgba_str(container_high, 0.85)};
@define-color toolbar_fg_color {text};
@define-color menu_bg_color {container_high};
@define-color menu_fg_color {text};
@define-color popover_bg_color {container_high};
@define-color popover_fg_color {text};
@define-color tooltip_bg_color {_shade(container_high, 0.10)};
@define-color tooltip_fg_color {text};
@define-color card_bg_color {_rgba_str(container_high, 0.78)};
@define-color card_fg_color {text};
@define-color card_border_color {_rgba_str(border, 0.30)};
@define-color scrollbar_bg_color {_rgba_str(variant, 0.40)};
@define-color scrollbar_slider_color {_rgba_str(selected_bg, 0.65)};
@define-color scrollbar_slider_hover_color {_rgba_str(selected_bg, 0.80)};
@define-color scrollbar_slider_active_color {selected_bg};

* {{
  -gtk-outline-radius: 12px;
  outline-color: alpha(currentColor, 0.15);
  outline-offset: -3px;
  outline-style: dashed;
  font-family: "{font_family}";
}}

*:selected, *:selected:focus {{
  background-color: @theme_selected_bg_color;
  color: @theme_selected_fg_color;
}}

/* Text selection in text views (textview, sourceview, entry, etc.) */
selection {{
  background-color: @theme_selected_bg_color;
  color: @theme_selected_fg_color;
}}

selection:focus-within {{
  background-color: @theme_selected_bg_color;
  color: @theme_selected_fg_color;
}}

*:disabled, *:insensitive {{
  color: @insensitive_fg_color;
  text-shadow: none;
}}

*:backdrop {{
  opacity: 0.85;
}}

/*********
 * Base  *
 *********/
window {{
  background-color: @window_bg_color;
  color: @window_fg_color;
}}

window.background, dialog.background, message-dialog.background {{
  background-color: @theme_bg_color;
  color: @theme_fg_color;
}}

.background {{
  background-color: @theme_bg_color;
  color: @theme_fg_color;
}}

/*************
 * Headerbar *
 *************/
headerbar, .titlebar {{
  background-image: none;
  background-color: @headerbar_bg_color;
  color: @headerbar_fg_color;
  border-bottom: 1px solid @headerbar_border_color;
  box-shadow: none;
  min-height: 48px;
  padding: 0 8px;
}}

headerbar:backdrop, .titlebar:backdrop {{
  background-color: @headerbar_backdrop_color;
}}

headerbar button, .titlebar button {{
  min-height: 32px;
  min-width: 32px;
  padding: 4px 8px;
}}

headerbar entry {{
  min-height: 30px;
}}

headerbar button.titlebutton {{
  min-height: 28px;
  min-width: 28px;
}}

/***********
 * Buttons *
 ***********/
button {{
  min-height: 34px;
  min-width: 34px;
  padding: 4px 16px;
  border-radius: 12px;
  border: 1px solid @borders;
  background-image: none;
  background-color: {container_high};
  color: {text};
  box-shadow: none;
  text-shadow: none;
  transition: all 120ms ease-out;
  -gtk-icon-shadow: none;
}}

button:hover {{
  background-color: {base_hover};
  border-color: {_shade(border, 0.10)};
}}

button:active, button:checked {{
  background-color: {selected_bg};
  color: {selected_fg};
  border-color: {selected_bg};
}}

button:disabled {{
  background-color: @insensitive_bg_color;
  color: @insensitive_fg_color;
  border-color: @unfocused_borders;
}}

button.suggested-action {{
  background-color: {selected_bg};
  color: {selected_fg};
  border-color: {selected_bg};
}}

button.suggested-action:hover {{
  background-color: {_shade(selected_bg, 0.12)};
}}

button.suggested-action:active {{
  background-color: {_shade(selected_bg, -0.10)};
}}

button.destructive-action {{
  background-color: {error};
  color: {on_error};
  border-color: {error};
}}

button.destructive-action:hover {{
  background-color: {_shade(error, 0.15)};
}}

button.flat {{
  background-color: transparent;
  border-color: transparent;
}}

button.flat:hover {{
  background-color: {_rgba_str(text, 0.08)};
}}

button.flat:checked {{
  background-color: {_rgba_str(selected_bg, 0.18)};
  color: {selected_bg};
  border-color: transparent;
}}

button.circular {{
  border-radius: 999px;
}}

button.link {{
  background-color: transparent;
  border-color: transparent;
  color: {selected_bg};
  text-decoration: underline;
}}

button.default {{
  border-color: {selected_bg};
  box-shadow: 0 0 0 1px {selected_bg};
}}

.linked button {{
  border-radius: 0;
  border-right-width: 0;
}}

.linked button:first-child {{
  border-radius: 12px 0 0 12px;
}}

.linked button:last-child {{
  border-radius: 0 12px 12px 0;
  border-right-width: 1px;
}}

.linked button:only-child {{
  border-radius: 12px;
  border-right-width: 1px;
}}

.linked.raised button {{
  border-radius: 12px;
  margin: 0 2px;
}}

/***********
 * Entries *
 ***********/
entry {{
  min-height: 34px;
  padding: 4px 12px;
  border-radius: 12px;
  border: 1px solid @borders;
  background-color: {base};
  color: {text};
  caret-color: {selected_bg};
  transition: all 120ms ease-out;
}}

entry:focus {{
  border-color: {selected_bg};
  box-shadow: 0 0 0 2px {_rgba_str(selected_bg, 0.25)};
  outline: none;
}}

entry:disabled {{
  background-color: @insensitive_bg_color;
  color: @insensitive_fg_color;
  border-color: @unfocused_borders;
}}

entry:read-only {{
  background-color: {_shade(base, -0.03)};
  border-style: dashed;
}}

entry.error {{
  border-color: {error};
}}

entry.warning {{
  border-color: {_shade(secondary, 0.15)};
}}

entry image {{
  color: {on_variant};
}}

/***************
 * Spinbuttons *
 ***************/
spinbutton {{
  border-radius: 12px;
  border: 1px solid @borders;
}}

spinbutton entry {{
  border: none;
  border-radius: 12px 0 0 12px;
  min-height: 32px;
}}

spinbutton button {{
  border: none;
  min-height: 32px;
  min-width: 28px;
  padding: 0;
  border-radius: 0;
}}

spinbutton button:last-child {{
  border-radius: 0 12px 12px 0;
}}

/*************
 * Combobox  *
 *************/
combobox button.combo {{
  min-height: 34px;
  padding: 4px 12px;
  border-radius: 12px;
}}

combobox arrow {{
  -gtk-icon-source: -gtk-icontheme("pan-down-symbolic");
  min-width: 16px;
  min-height: 16px;
}}

/*************
 * Switches  *
 *************/
switch {{
  min-width: 48px;
  min-height: 26px;
  border-radius: 999px;
  background-color: {variant};
  border: 1px solid @borders;
  transition: all 160ms ease-out;
}}

switch:checked {{
  background-color: {selected_bg};
  border-color: {selected_bg};
}}

switch slider {{
  min-width: 22px;
  min-height: 22px;
  border-radius: 999px;
  background-color: {text};
  border: none;
  margin: 1px;
  transition: all 120ms ease-out;
}}

switch:checked slider {{
  background-color: {selected_fg};
  margin-left: 24px;
}}

switch:disabled slider {{
  background-color: @insensitive_fg_color;
}}

/****************
 * Check/Radio  *
 ****************/
check, radio {{
  min-width: 20px;
  min-height: 20px;
  border-radius: 4px;
  border: 2px solid @borders;
  background-color: transparent;
  transition: all 100ms ease-out;
}}

radio {{
  border-radius: 999px;
}}

check:checked, radio:checked {{
  background-color: {selected_bg};
  border-color: {selected_bg};
  -gtk-icon-source: -gtk-icontheme("object-select-symbolic");
}}

check:indeterminate {{
  background-color: {selected_bg};
  border-color: {selected_bg};
  -gtk-icon-source: -gtk-icontheme("list-remove-symbolic");
}}

check:disabled, radio:disabled {{
  border-color: @unfocused_borders;
}}

check:disabled:checked, radio:disabled:checked {{
  background-color: @insensitive_fg_color;
  border-color: @insensitive_fg_color;
}}

/*********
 * Scale *
 *********/
scale {{
  min-height: 28px;
}}

scale trough {{
  min-height: 6px;
  border-radius: 999px;
  background-color: {variant};
  border: none;
}}

scale trough highlight {{
  min-height: 6px;
  border-radius: 999px;
  background-color: {selected_bg};
}}

scale slider {{
  min-width: 18px;
  min-height: 18px;
  border-radius: 999px;
  background-color: {selected_bg};
  border: 3px solid {bg};
  box-shadow: 0 1px 4px {_rgba_str("#000000", 0.30)};
  transition: all 120ms ease-out;
}}

scale slider:hover {{
  transform: scale(1.15);
  box-shadow: 0 2px 8px {_rgba_str("#000000", 0.35)};
}}

scale marks {{
  color: {on_variant};
}}

scale value {{
  color: {on_variant};
  font-size: 0.82em;
}}

/*****************
 * Progress Bars *
 *****************/
progressbar {{
  min-height: 6px;
  border-radius: 999px;
}}

progressbar trough {{
  min-height: 6px;
  border-radius: 999px;
  background-color: {variant};
  border: none;
}}

progressbar progress {{
  min-height: 6px;
  border-radius: 999px;
  background-color: {selected_bg};
}}

progressbar.vertical trough {{
  min-width: 6px;
  min-height: 80px;
}}

progressbar.vertical progress {{
  min-width: 6px;
}}

progressbar.oscillating progress {{
  background-image: linear-gradient(
    to right,
    {selected_bg},
    {_shade(selected_bg, 0.30)},
    {selected_bg}
  );
  background-size: 200% 100%;
}}

/***************
 * Level Bars  *
 ***************/
levelbar {{
  min-height: 6px;
  border-radius: 999px;
}}

levelbar trough {{
  min-height: 6px;
  border-radius: 999px;
  background-color: {variant};
  border: none;
}}

levelbar block {{
  min-height: 6px;
  border-radius: 999px;
  margin: 0 1px;
}}

levelbar block.fill-block {{
  background-color: {selected_bg};
}}

levelbar block.empty {{
  background-color: {variant};
}}

levelbar block.low {{
  background-color: {_shade(secondary, 0.15)};
}}

levelbar block.high {{
  background-color: {selected_bg};
}}

/***************
 * Scrollbars  *
 ***************/
scrollbar {{
  background-color: transparent;
  border: none;
}}

scrollbar slider {{
  min-width: 6px;
  min-height: 40px;
  border-radius: 999px;
  background-color: @scrollbar_slider_color;
  border: none;
  transition: all 120ms ease-out;
}}

scrollbar slider:hover {{
  background-color: @scrollbar_slider_hover_color;
  min-width: 8px;
}}

scrollbar slider:active {{
  background-color: @scrollbar_slider_active_color;
}}

scrollbar trough {{
  background-color: @scrollbar_bg_color;
  border: none;
  border-radius: 999px;
  margin: 4px;
}}

scrollbar.vertical slider {{
  min-width: 6px;
}}

scrollbar.horizontal slider {{
  min-height: 6px;
}}

scrollbar.vertical {{
  min-width: 14px;
}}

scrollbar.horizontal {{
  min-height: 14px;
}}

scrollbar button {{
  min-width: 0;
  min-height: 0;
  padding: 0;
  border: none;
  background: none;
}}

/*****************
 * Tree/List View *
 *****************/
treeview {{
  background-color: {base};
  color: {text};
}}

treeview.view {{
  border-left-color: {_rgba_str(border, 0.30)};
  border-top-color: {_rgba_str(border, 0.15)};
  padding: 4px 6px;
}}

treeview.view:selected {{
  background-color: {selected_bg};
  color: {selected_fg};
  border-radius: 8px;
}}

treeview.view:even {{
  background-color: {_rgba_str(base, 0.85)};
}}

treeview.view:odd {{
  background-color: {_shade(base, -0.02)};
}}

treeview header button {{
  min-height: 32px;
  padding: 2px 8px;
  border-radius: 0;
  border: none;
  border-bottom: 2px solid {_rgba_str(border, 0.30)};
  background-color: {_shade(base, -0.03)};
  color: {text};
}}

treeview header button:hover {{
  background-color: {_shade(base, -0.06)};
  border-bottom-color: {selected_bg};
}}

column-header {{
  background-color: {_shade(base, -0.03)};
}}

column-header button {{
  min-height: 32px;
  padding: 2px 8px;
  border: none;
  border-bottom: 2px solid {_rgba_str(border, 0.30)};
}}

/**************
 * Icon View  *
 **************/
iconview {{
  background-color: {base};
  color: {text};
}}

iconview:selected {{
  background-color: {_rgba_str(selected_bg, 0.25)};
  color: {text};
  border-radius: 12px;
}}

iconview:focus {{
  outline: 2px solid {_rgba_str(selected_bg, 0.40)};
}}

/*************
 * Text View *
 *************/
textview {{
  background-color: {base};
  color: {text};
  border-radius: 12px;
}}

textview text {{
  background-color: transparent;
  color: {text};
  caret-color: {selected_bg};
  font-family: "{mono_font_family}";
}}

textview border {{
  border-color: @borders;
}}

/*************
 * SourceView (Mousepad, Gedit, etc.) *
 *************/
sourceview {{
  background-color: {base};
  color: {text};
  border-radius: 12px;
}}

sourceview text {{
  background-color: {base};
  color: {text};
  caret-color: {selected_bg};
  font-family: "{mono_font_family}";
}}

sourceview border {{
  border-color: @borders;
}}

/***********
 * Frames  *
 ***********/
frame {{
  border-radius: 12px;
}}

frame > border {{
  border: 1px solid {_rgba_str(border, 0.30)};
  border-radius: 12px;
  padding: 4px;
}}

frame.flat > border {{
  border: none;
}}

/***************
 * Notebooks   *
 ***************/
notebook {{
  background-color: {bg};
  color: {text};
  border-radius: 12px;
}}

notebook header {{
  background-color: {container_high};
  border: none;
  padding: 2px;
}}

notebook header.top {{
  border-radius: 12px 12px 0 0;
}}

notebook tab {{
  min-height: 32px;
  min-width: 48px;
  padding: 4px 12px;
  border: none;
  border-radius: 10px;
  background-color: transparent;
  color: {on_variant};
  transition: all 120ms ease-out;
}}

notebook tab:hover {{
  background-color: {_rgba_str(text, 0.06)};
  color: {text};
}}

notebook tab:checked {{
  background-color: {_rgba_str(selected_bg, 0.16)};
  color: {selected_bg};
}}

notebook tab button {{
  min-height: 20px;
  min-width: 20px;
  padding: 0;
  border-radius: 999px;
}}

notebook tab.reorderable-page {{
  border-left: 2px solid transparent;
}}

notebook tab.dragging {{
  opacity: 0.60;
}}

notebook arrow {{
  min-height: 24px;
  min-width: 24px;
  border-radius: 999px;
}}

/************
 * Toolbars *
 ************/
toolbar {{
  background-color: @toolbar_bg_color;
  color: @toolbar_fg_color;
  padding: 4px;
  border: none;
}}

toolbar button {{
  min-height: 30px;
  min-width: 30px;
  padding: 2px 8px;
}}

toolbar separator {{
  min-width: 1px;
  min-height: 24px;
  background-color: {_rgba_str(border, 0.35)};
  margin: 4px 2px;
}}

/************
 * Menu Bar *
 ************/
menubar {{
  background-color: @menubar_bg_color;
  color: @menubar_fg_color;
  padding: 2px;
}}

menubar:backdrop {{
  opacity: 0.80;
}}

menubar > item {{
  padding: 6px 10px;
  border-radius: 8px;
}}

menubar > item:hover {{
  background-color: {_rgba_str(text, 0.08)};
}}

/*********
 * Menus *
 *********/
menu {{
  background-color: @menu_bg_color;
  color: @menu_fg_color;
  border: 1px solid {_rgba_str(border, 0.60)};
  border-radius: 12px;
  padding: 4px;
  box-shadow: 0 4px 16px {_rgba_str("#000000", 0.30)};
}}

menu:backdrop {{
  opacity: 0.85;
}}

menuitem {{
  padding: 8px 32px 8px 12px;
  border-radius: 8px;
  min-height: 24px;
}}

menuitem:hover {{
  background-color: {_rgba_str(selected_bg, 0.16)};
  color: {text};
}}

menuitem:disabled {{
  color: @insensitive_fg_color;
}}

menuitem accelerator {{
  color: {on_variant};
  margin-left: 16px;
}}

menu separator {{
  min-height: 1px;
  margin: 4px 8px;
  background-color: {_rgba_str(border, 0.30)};
}}

/************
 * Popovers *
 ************/
popover {{
  background-color: @popover_bg_color;
  color: @popover_fg_color;
  border: 1px solid {_rgba_str(border, 0.50)};
  border-radius: 14px;
  box-shadow: 0 4px 20px {_rgba_str("#000000", 0.35)};
}}

popover.background {{
  padding: 4px;
}}

popover.background > arrow {{
  min-width: 16px;
  min-height: 16px;
}}

popover modelbutton {{
  padding: 8px 16px;
  border-radius: 8px;
  min-height: 28px;
}}

popover modelbutton:hover {{
  background-color: {_rgba_str(selected_bg, 0.14)};
}}

popover modelbutton:selected {{
  background-color: {selected_bg};
  color: {selected_fg};
  border-radius: 8px;
}}

popover list {{
  background: none;
}}

/*************
 * Tooltips  *
 *************/
tooltip {{
  border-radius: 10px;
  padding: 4px;
}}

tooltip.background {{
  background-color: @tooltip_bg_color;
  color: @tooltip_fg_color;
  border: 1px solid {_rgba_str(border, 0.35)};
  border-radius: 10px;
}}

tooltip label {{
  padding: 4px 8px;
  color: @tooltip_fg_color;
  font-size: 0.92em;
}}

/***************
 * Status Bar  *
 ***************/
statusbar {{
  background-color: {_rgba_str(container_high, 0.60)};
  color: {text};
  border-top: 1px solid {_rgba_str(border, 0.20)};
  padding: 2px 8px;
}}

statusbar label {{
  padding: 2px 6px;
}}

/**************
 * Info Bars  *
 **************/
infobar {{
  border: none;
  border-radius: 10px;
  margin: 4px 0;
}}

infobar.info {{
  background-color: {_rgba_str(primary_cont, 0.60)};
  color: {on_primary_cont};
}}

infobar.warning {{
  background-color: {_rgba_str(_shade(secondary, 0.15), 0.50)};
  color: {text};
}}

infobar.error {{
  background-color: {_rgba_str(error, 0.20)};
  color: {error};
}}

infobar.question {{
  background-color: {_rgba_str(tertiary, 0.25)};
  color: {on_tertiary};
}}

infobar label {{
  padding: 6px 8px;
}}

infobar button {{
  min-height: 28px;
  min-width: 28px;
  padding: 2px 10px;
}}

/***************
 * Action Bar  *
 ***************/
actionbar {{
  background-color: {container_high};
  color: {text};
  border-top: 1px solid {_rgba_str(border, 0.25)};
  padding: 8px;
}}

/*********
 * Paned *
 *********/
paned > separator {{
  min-width: 2px;
  min-height: 2px;
  background-color: {_rgba_str(border, 0.25)};
  margin: 2px;
  border-radius: 999px;
  transition: all 120ms ease-out;
}}

paned > separator:hover {{
  background-color: {_rgba_str(selected_bg, 0.40)};
  min-width: 4px;
}}

/**************
 * Calendar   *
 **************/
calendar {{
  background-color: {base};
  color: {text};
  border: 1px solid {_rgba_str(border, 0.30)};
  border-radius: 12px;
  padding: 4px;
}}

calendar.header {{
  background-color: {container_high};
  border: none;
  border-radius: 8px;
  padding: 4px;
}}

calendar:selected {{
  background-color: {selected_bg};
  color: {selected_fg};
  border-radius: 999px;
}}

calendar.button {{
  min-height: 28px;
  min-width: 28px;
  border-radius: 999px;
}}

calendar.highlight {{
  color: {on_variant};
  font-weight: bold;
}}

/*************
 * Expanders *
 *************/
expander {{
  color: {text};
}}

expander arrow {{
  min-width: 16px;
  min-height: 16px;
}}

expander arrow:checked {{
  -gtk-icon-source: -gtk-icontheme("pan-down-symbolic");
}}

/*********
 * Links *
 *********/
link {{
  color: {selected_bg};
  text-decoration: underline;
}}

link:hover {{
  color: {_shade(selected_bg, 0.20)};
}}

link:visited {{
  color: {secondary};
}}

/*************
 * Flow Box  *
 *************/
flowbox {{
  background-color: transparent;
}}

flowbox child {{
  padding: 4px;
  border-radius: 12px;
}}

flowbox child:selected {{
  background-color: {_rgba_str(selected_bg, 0.18)};
  outline: 2px solid {_rgba_str(selected_bg, 0.40)};
}}

/************
 * List Box *
 ************/
list {{
  background-color: {base};
  color: {text};
  border-radius: 12px;
}}

list row {{
  padding: 8px 12px;
  border-radius: 8px;
  min-height: 36px;
  transition: all 80ms ease-out;
}}

list row:hover {{
  background-color: {_rgba_str(text, 0.04)};
}}

list row:selected {{
  background-color: {_rgba_str(selected_bg, 0.16)};
  color: {text};
}}

list row:selected:hover {{
  background-color: {_rgba_str(selected_bg, 0.22)};
}}

/*****************
 * Stack Switcher *
 *****************/
stackswitcher {{
  background-color: {_rgba_str(container_high, 0.60)};
  border-radius: 999px;
  padding: 2px;
}}

stackswitcher button {{
  min-height: 28px;
  min-width: 48px;
  padding: 2px 12px;
  border: none;
  border-radius: 999px;
  background-color: transparent;
  color: {on_variant};
}}

stackswitcher button:checked {{
  background-color: {selected_bg};
  color: {selected_fg};
}}

/****************
 * Color Swatch *
 ****************/
colorswatch {{
  border-radius: 999px;
  border: 2px solid {_rgba_str(border, 0.30)};
}}

colorswatch:selected {{
  border-color: {selected_bg};
  outline: 2px solid {_rgba_str(selected_bg, 0.40)};
}}

/*************
 * Separator *
 *************/
separator {{
  min-width: 1px;
  min-height: 1px;
  background-color: {_rgba_str(border, 0.30)};
}}

separator.vertical {{
  min-width: 1px;
  min-height: 24px;
  margin: 0 4px;
}}

separator.horizontal {{
  min-height: 1px;
  min-width: 24px;
  margin: 4px 0;
}}

/*******
 * OSD *
 *******/
.osd {{
  background-color: {_rgba_str(bg, 0.85)};
  color: {fg};
  border: 1px solid {_rgba_str(border, 0.40)};
  border-radius: 14px;
  padding: 8px;
}}

/**************
 * Rubberband *
 **************/
rubberband, .rubberband {{
  background-color: {_rgba_str(selected_bg, 0.20)};
  border: 1px solid {selected_bg};
  border-radius: 4px;
}}

/********
 * View *
 ********/
.view {{
  background-color: @view_bg_color;
  color: @view_fg_color;
}}

.view:selected {{
  background-color: {selected_bg};
  color: {selected_fg};
  border-radius: 8px;
}}

.content-view {{
  background-color: {bg};
}}

/***************
 * Search Bar  *
 ***************/
searchbar {{
  background-color: {container_high};
  border-bottom: 1px solid {_rgba_str(border, 0.25)};
  padding: 6px;
}}

/********
 * Misc *
 ********/
label:disabled {{
  color: @insensitive_fg_color;
}}

.dim-label {{
  opacity: 0.65;
}}

.background .titlebar {{
  border-radius: 12px 12px 0 0;
}}

.titlebutton {{
  min-height: 24px;
  min-width: 24px;
  border-radius: 999px;
  padding: 2px;
}}

messagedialog .dialog-action-area button {{
  padding: 8px 24px;
  min-height: 36px;
  border-radius: 0;
  border: none;
  border-top: 1px solid {_rgba_str(border, 0.25)};
  border-right: 1px solid {_rgba_str(border, 0.15)};
}}

messagedialog .dialog-action-area button:first-child {{
  border-radius: 0 0 0 12px;
}}

messagedialog .dialog-action-area button:last-child {{
  border-right: none;
  border-radius: 0 0 12px 0;
}}

messagedialog .dialog-action-area button:only-child {{
  border-radius: 0 0 12px 12px;
}}

.dnd {{
  border: 2px dashed {_rgba_str(selected_bg, 0.50)};
  border-radius: 12px;
}}

overlay {{
  background-color: transparent;
}}
""".strip()
        + "\n"
    )


def _hanauta_qt5ct_colors(palette: dict[str, str]) -> str:
    bg = palette["background"]
    fg = palette["on_background"]
    base = palette["surface_container"]
    text = palette["on_surface"]
    selected_bg = palette["primary"]
    selected_fg = palette["on_primary"]
    border = palette["outline"]
    surface = palette["surface"]
    container_high = palette["surface_container_high"]
    variant = palette["surface_variant"]
    on_variant = palette["on_surface_variant"]
    error = palette["error"]
    on_error = palette["on_error"]
    primary_cont = palette["primary_container"]
    on_primary_cont = palette["on_primary_container"]
    secondary = palette["secondary"]
    on_secondary = palette["on_secondary"]
    tertiary = palette["tertiary"]
    on_tertiary = palette["on_tertiary"]

    return f"""# Hanauta Qt Color Scheme - generated from theme palette
# Compatible with qt5ct/qt6ct
[ColorScheme]
author=Hanauta
contrast=1

# Window background / foreground
window_color={bg}
window_text_color={fg}

# Base (input fields, list backgrounds)
base_color={base}
base_text_color={text}

# Button
button_color={container_high}
button_text_color={text}

# Highlight (selection)
highlight_color={selected_bg}
highlighted_text_color={selected_fg}

# Tooltip
tooltip_base_color={_shade(container_high, 0.10)}
tooltip_text_color={text}

# Links
link_color={selected_bg}
link_visited_color={secondary}

# Desktop (for completeness)
alternate_base_color={_shade(base, -0.03)}

# Selection frame (focus indicators)
selection_color={_rgba_str(selected_bg, 0.30)}

# Inactive / disabled
disabled_text_color={_rgba_str(text, 0.45)}
disabled_window_color={_rgba_str(bg, 0.55)}
disabled_base_color={_rgba_str(base, 0.55)}
disabled_button_color={_rgba_str(container_high, 0.55)}

# Scrollbar
scrollbar_bg_color={variant}
scrollbar_slider_color={selected_bg}

# Active title bar
active_title_bg={selected_bg}
active_title_fg={selected_fg}
active_title_border={selected_bg}

# Inactive title bar
inactive_title_bg={container_high}
inactive_title_fg={text}
inactive_title_border={_rgba_str(border, 0.40)}

# Sidebar
sidebar_bg={base}
sidebar_text={text}
sidebar_selection_bg={_rgba_str(selected_bg, 0.16)}
sidebar_selection_fg={text}
"""


def _hanauta_kvantum_theme(palette: dict[str, str],
                           font_family: str = "Rubik",
                           mono_font_family: str = "JetBrains Mono") -> dict[str, str]:
    bg = palette["background"]
    fg = palette["on_background"]
    base = palette["surface_container"]
    text = palette["on_surface"]
    selected_bg = palette["primary"]
    selected_fg = palette["on_primary"]
    border = palette["outline"]
    container_high = palette["surface_container_high"]
    variant = palette["surface_variant"]
    secondary = palette["secondary"]
    error = palette["error"]

    kvantum_kvconfig = f"""# Hanauta Kvantum theme - generated from theme palette
# Place in ~/.config/Kvantum/Hanauta-ThemeName/

[General]
theme=Rounded

[Appearance]
ColorScheme=Hanauta
Style=Kvantum
CustomDecorations=true
BackgroundColor={bg}
ForegroundColor={fg}

[Fonts]
fixed={mono_font_family},10,-1,5,400,0,0,0,0,0
general={font_family},10,-1,5,400,0,0,0,0,0

[Colors]
Window={bg}
WindowText={fg}
Base={base}
Text={text}
Button={container_high}
ButtonText={text}
Highlight={selected_bg}
HighlightText={selected_fg}
TooltipBase={_shade(container_high, 0.10)}
TooltipText={text}
Link={selected_bg}
LinkVisited={secondary}

[Hacks]
transparent_borders=false
disable_ratio=1
small_icon_size=16
large_icon_size=32
button_icon_size=16
toolbar_icon_size=22
listview_icon_size=22
icon_width=16
icon_height=16

[Opacity]
Menu=0.92
Popup=0.94
Tooltip=0.96
Window=1.00
Sidebar=0.96
"""

    return {"Kvantum.kvconfig": kvantum_kvconfig}


def _write_index_theme(theme_dir: Path, display_name: str, gtk_theme: str,
                       icon_theme: str = "Papirus") -> None:
    _ensure_parent(theme_dir / "index.theme")
    (theme_dir / "index.theme").write_text(
        "\n".join(
            [
                "[Desktop Entry]",
                "Type=X-GNOME-Metatheme",
                f"Name={display_name}",
                "Comment=Hanauta managed theme",
                "Encoding=UTF-8",
                "",
                "[X-GNOME-Metatheme]",
                f"GtkTheme={gtk_theme}",
                f"IconTheme={icon_theme}",
                "CursorTheme=Adwaita",
                "ButtonLayout=menu:minimize,maximize,close",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _write_qt_theme_files(theme_dir: Path, palette: dict[str, str], theme_name: str,
                          font_family: str = "Rubik",
                          mono_font_family: str = "JetBrains Mono") -> None:
    qt_dir = theme_dir / "qt"
    qt_dir.mkdir(parents=True, exist_ok=True)

    (qt_dir / "colors.conf").write_text(
        _hanauta_qt5ct_colors(palette), encoding="utf-8"
    )

    kvantum_dir = theme_dir / "Kvantum"
    kvantum_dir.mkdir(parents=True, exist_ok=True)
    kvantum_files = _hanauta_kvantum_theme(palette, font_family=font_family,
                                            mono_font_family=mono_font_family)
    for filename, content in kvantum_files.items():
        (kvantum_dir / filename).write_text(content, encoding="utf-8")

    (qt_dir / "qt5ct_color_scheme.conf").write_text(
        _hanauta_qt5ct_colors(palette), encoding="utf-8"
    )


def _hanauta_gtk2_rc(palette: dict[str, str],
                     font_family: str = "Rubik",
                     mono_font_family: str = "JetBrains Mono") -> str:
    bg = palette["background"]
    fg = palette["on_background"]
    base = palette["surface_container"]
    text = palette["on_surface"]
    selected_bg = palette["primary"]
    selected_fg = palette["on_primary"]
    border = palette["outline"]
    container_high = palette["surface_container_high"]
    variant = palette["surface_variant"]
    on_variant = palette["on_surface_variant"]
    error = palette["error"]
    on_error = palette["on_error"]

    def hex_to_rgb(c: str) -> tuple:
        return int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)

    def shade(c: str, factor: float) -> str:
        r, g, b = hex_to_rgb(c)
        if factor >= 0:
            r = int(r + (255 - r) * factor)
            g = int(g + (255 - g) * factor)
            b = int(b + (255 - b) * factor)
        else:
            r = int(r * (1 + factor))
            g = int(g * (1 + factor))
            b = int(b * (1 + factor))
        return f"#{r:02x}{g:02x}{b:02x}"

    def rgba(c: str, alpha: float) -> str:
        r, g, b = hex_to_rgb(c)
        return f"rgba({r}, {g}, {b}, {alpha:.2f})"

    base_hover = shade(base, -0.05)
    base_active = shade(base, -0.10)
    selected_hover = shade(selected_bg, 0.12)
    selected_active = shade(selected_bg, -0.10)
    error_hover = shade(error, 0.15)
    variant_hover = shade(variant, 0.05)

    return (
        f"""
style "hanauta-default" {{
    GtkWidget::focus-line-width = 1
    GtkWidget::focus-padding = 1
    GtkWidget::interior-focus = 1

    bg[NORMAL] = "{bg}"
    bg[PRELIGHT] = "{base_hover}"
    bg[ACTIVE] = "{base_active}"
    bg[SELECTED] = "{selected_bg}"
    bg[INSENSITIVE] = "{rgba(bg, 0.50)}"

    fg[NORMAL] = "{fg}"
    fg[PRELIGHT] = "{text}"
    fg[ACTIVE] = "{selected_fg}"
    fg[SELECTED] = "{selected_fg}"
    fg[INSENSITIVE] = "{rgba(text, 0.45)}"

    text[NORMAL] = "{text}"
    text[PRELIGHT] = "{text}"
    text[ACTIVE] = "{selected_fg}"
    text[SELECTED] = "{selected_fg}"
    text[INSENSITIVE] = "{rgba(text, 0.45)}"

    base[NORMAL] = "{base}"
    base[PRELIGHT] = "{base_hover}"
    base[ACTIVE] = "{base_active}"
    base[SELECTED] = "{selected_bg}"
    base[INSENSITIVE] = "{rgba(base, 0.50)}"

    font_name = "{font_family} 10"
}}

style "hanauta-button" = "hanauta-default" {{
    xthickness = 6
    ythickness = 4

    bg[NORMAL] = "{container_high}"
    bg[PRELIGHT] = "{base_hover}"
    bg[ACTIVE] = "{selected_bg}"
    bg[SELECTED] = "{selected_bg}"
    bg[INSENSITIVE] = "{rgba(bg, 0.50)}"

    fg[NORMAL] = "{text}"
    fg[PRELIGHT] = "{text}"
    fg[ACTIVE] = "{selected_fg}"
    fg[SELECTED] = "{selected_fg}"
    fg[INSENSITIVE] = "{rgba(text, 0.45)}"
}}

style "hanauta-entry" = "hanauta-default" {{
    xthickness = 8
    ythickness = 6

    bg[NORMAL] = "{base}"
    bg[PRELIGHT] = "{base}"
    bg[ACTIVE] = "{base}"
    bg[SELECTED] = "{selected_bg}"
    bg[INSENSITIVE] = "{rgba(base, 0.50)}"

    fg[NORMAL] = "{text}"
    fg[PRELIGHT] = "{text}"
    fg[ACTIVE] = "{selected_fg}"
    fg[SELECTED] = "{selected_fg}"
    fg[INSENSITIVE] = "{rgba(text, 0.45)}"
}}

style "hanauta-combobox" = "hanauta-entry" {{
    xthickness = 6
    ythickness = 4
}}

style "hanauta-scale" = "hanauta-default" {{
    bg[NORMAL] = "{variant}"
    bg[PRELIGHT] = "{variant_hover}"
    bg[ACTIVE] = "{selected_bg}"
    bg[SELECTED] = "{selected_bg}"
}}

style "hanauta-scrollbar" = "hanauta-default" {{
    bg[NORMAL] = "{rgba(variant, 0.40)}"
    bg[PRELIGHT] = "{rgba(selected_bg, 0.65)}"
    bg[ACTIVE] = "{selected_bg}"
    bg[SELECTED] = "{selected_bg}"
}}

style "hanauta-menu" = "hanauta-default" {{
    bg[NORMAL] = "{container_high}"
    bg[PRELIGHT] = "{rgba(selected_bg, 0.16)}"
    bg[ACTIVE] = "{selected_bg}"
    bg[SELECTED] = "{selected_bg}"
    bg[INSENSITIVE] = "{rgba(container_high, 0.50)}"

    fg[NORMAL] = "{text}"
    fg[PRELIGHT] = "{text}"
    fg[ACTIVE] = "{selected_fg}"
    fg[SELECTED] = "{selected_fg}"
    fg[INSENSITIVE] = "{rgba(text, 0.45)}"
}}

style "hanauta-tooltip" = "hanauta-default" {{
    bg[NORMAL] = "{shade(container_high, 0.10)}"
    fg[NORMAL] = "{text}"
    xthickness = 6
    ythickness = 4
}}

style "hanauta-notebook" = "hanauta-default" {{
    bg[NORMAL] = "{bg}"
    bg[PRELIGHT] = "{rgba(text, 0.06)}"
    bg[ACTIVE] = "{rgba(selected_bg, 0.16)}"
    bg[SELECTED] = "{rgba(selected_bg, 0.16)}"
    xthickness = 2
    ythickness = 2
}}

style "hanauta-progressbar" = "hanauta-default" {{
    bg[NORMAL] = "{variant}"
    bg[PRELIGHT] = "{variant}"
    bg[ACTIVE] = "{selected_bg}"
    bg[SELECTED] = "{selected_bg}"
}}

style "hanauta-treeview" = "hanauta-default" {{
    bg[NORMAL] = "{base}"
    bg[PRELIGHT] = "{rgba(base, 0.85)}"
    bg[ACTIVE] = "{selected_bg}"
    bg[SELECTED] = "{selected_bg}"
    bg[INSENSITIVE] = "{rgba(base, 0.50)}"

    fg[NORMAL] = "{text}"
    fg[PRELIGHT] = "{text}"
    fg[ACTIVE] = "{selected_fg}"
    fg[SELECTED] = "{selected_fg}"
    fg[INSENSITIVE] = "{rgba(text, 0.45)}"
}}

style "hanauta-frame" = "hanauta-default" {{
    bg[NORMAL] = "{bg}"
    fg[NORMAL] = "{text}"
}}

style "hanauta-toolbar" = "hanauta-default" {{
    bg[NORMAL] = "{rgba(container_high, 0.85)}"
    bg[PRELIGHT] = "{rgba(text, 0.08)}"
    bg[ACTIVE] = "{rgba(selected_bg, 0.18)}"
    bg[SELECTED] = "{rgba(selected_bg, 0.18)}"
}}

style "hanauta-menubar" = "hanauta-default" {{
    bg[NORMAL] = "{container_high}"
    bg[PRELIGHT] = "{rgba(text, 0.08)}"
    bg[ACTIVE] = "{rgba(selected_bg, 0.16)}"
    bg[SELECTED] = "{rgba(selected_bg, 0.16)}"
}}

style "hanauta-statusbar" = "hanauta-default" {{
    bg[NORMAL] = "{rgba(container_high, 0.60)}"
    fg[NORMAL] = "{text}"
}}

style "hanauta-paned" = "hanauta-default" {{
    bg[NORMAL] = "{rgba(border, 0.25)}"
    bg[PRELIGHT] = "{rgba(selected_bg, 0.40)}"
    bg[ACTIVE] = "{selected_bg}"
}}

class "GtkWidget" style "hanauta-default"
class "GtkButton" style "hanauta-button"
class "GtkToggleButton" style "hanauta-button"
class "GtkCheckButton" style "hanauta-button"
class "GtkRadioButton" style "hanauta-button"
class "GtkEntry" style "hanauta-entry"
class "GtkSpinButton" style "hanauta-entry"
class "GtkComboBox" style "hanauta-combobox"
class "GtkComboBoxEntry" style "hanauta-combobox"
class "GtkScale" style "hanauta-scale"
class "GtkHScale" style "hanauta-scale"
class "GtkVScale" style "hanauta-scale"
class "GtkScrollbar" style "hanauta-scrollbar"
class "GtkHScrollbar" style "hanauta-scrollbar"
class "GtkVScrollbar" style "hanauta-scrollbar"
class "GtkMenu" style "hanauta-menu"
class "GtkMenuItem" style "hanauta-menu"
class "GtkMenuBar" style "hanauta-menubar"
class "GtkToolbar" style "hanauta-toolbar"
class "GtkHandleBox" style "hanauta-toolbar"
class "GtkTooltip" style "hanauta-tooltip"
class "GtkNotebook" style "hanauta-notebook"
class "GtkProgressBar" style "hanauta-progressbar"
class "GtkTreeView" style "hanauta-treeview"
class "GtkFrame" style "hanauta-frame"
class "GtkStatusbar" style "hanauta-statusbar"
class "GtkPaned" style "hanauta-paned"
class "GtkSeparator" style "hanauta-default"
class "GtkSourceView" style "hanauta-entry"
class "GtkSourceBuffer" style "hanauta-entry"

# Suggested action button
style "hanauta-suggested-button" = "hanauta-button" {{
    bg[NORMAL] = "{selected_bg}"
    bg[PRELIGHT] = "{selected_hover}"
    bg[ACTIVE] = "{selected_active}"
    fg[NORMAL] = "{selected_fg}"
    fg[PRELIGHT] = "{selected_fg}"
    fg[ACTIVE] = "{selected_fg}"
}}

# Destructive action button
style "hanauta-destructive-button" = "hanauta-button" {{
    bg[NORMAL] = "{error}"
    bg[PRELIGHT] = "{error_hover}"
    bg[ACTIVE] = "{shade(error, -0.10)}"
    fg[NORMAL] = "{on_error}"
    fg[PRELIGHT] = "{on_error}"
    fg[ACTIVE] = "{on_error}"
}}

widget_class "*<GtkButton>*<GtkLabel>" style "hanauta-button"
widget_class "*<GtkButton>*<GtkImage>" style "hanauta-button"

# Suggested action buttons (often used for OK, Apply, etc.)
widget "*dialog*action_area*button*" style "hanauta-suggested-button"
widget "*Dialog*action_area*button*" style "hanauta-suggested-button"
widget "*MessageDialog*action_area*button*" style "hanauta-suggested-button"

# Destructive action buttons (Delete, Remove, etc.)
widget "*dialog*action_area*button.destructive*" style "hanauta-destructive-button"
widget "*Dialog*action_area*button.destructive*" style "hanauta-destructive-button"
widget "*MessageDialog*action_area*button.destructive*" style "hanauta-destructive-button"

# Panel/statusbar
widget_class "*Panel*" style "hanauta-statusbar"
widget_class "*Applet*" style "hanauta-statusbar"

# Tooltips
widget "gtk-tooltip*" style "hanauta-tooltip"
""".strip()
        + "\n"
    )


def ensure_builtin_hanauta_gtk_theme(theme_key: str) -> str:
    metadata = THEME_LIBRARY[theme_key]
    theme_name = str(metadata["gtk_theme"])
    palette = dict(metadata["palette"])
    icon_theme = str(metadata.get("icon_theme", "Papirus"))
    fonts = metadata.get("fonts", HANAUTA_FONT_PROFILE)
    font_family = fonts.get("ui_font_family", "Rubik")
    mono_font_family = fonts.get("mono_font_family", "JetBrains Mono")
    theme_dir = THEMES_HOME / theme_name
    for gtk_dir_name in ("gtk-2.0", "gtk-3.0", "gtk-4.0"):
        gtk_dir = theme_dir / gtk_dir_name
        gtk_dir.mkdir(parents=True, exist_ok=True)
        if gtk_dir_name == "gtk-2.0":
            (gtk_dir / "gtkrc").write_text(
                _hanauta_gtk2_rc(palette, font_family=font_family, mono_font_family=mono_font_family),
                encoding="utf-8"
            )
        else:
            (gtk_dir / "gtk.css").write_text(
                _hanauta_gtk_css(palette, font_family=font_family, mono_font_family=mono_font_family),
                encoding="utf-8"
            )
    _write_index_theme(theme_dir, str(metadata["label"]), theme_name, icon_theme=icon_theme)
    _write_qt_theme_files(theme_dir, palette, theme_name,
                          font_family=font_family, mono_font_family=mono_font_family)
    return theme_name


def ensure_dracula_gtk_theme() -> str:
    from settings_page.theme_data import THEME_LIBRARY
    metadata = THEME_LIBRARY["dracula"]
    target = THEMES_HOME / str(metadata["gtk_theme"])
    ROOT = Path(__file__).resolve().parents[2].parents[1]
    source = ROOT / "hanauta" / "vendor" / "themes" / "dracula-gtk"
    if not target.exists():
        _copytree_clean(source, target)
    return str(metadata["gtk_theme"])


def ensure_retrowave_gtk_theme() -> str:
    from settings_page.theme_data import THEME_LIBRARY
    metadata = THEME_LIBRARY["retrowave"]
    ROOT = Path(__file__).resolve().parents[2].parents[1]
    source = (
        ROOT / "hanauta" / "vendor" / "themes" / "retrowave-theme" / "src" / "retrowave"
    )
    target = THEMES_HOME / str(metadata["gtk_theme"])
    if target.exists() or target.is_symlink():
        shutil.rmtree(target, ignore_errors=True)
    target.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / "index.theme", target / "index.theme")
    if (source / "gtk-2.0").exists():
        _copytree_clean(source / "gtk-2.0", target / "gtk-2.0")
    gtk3_source = source / "gtk-3.0"
    gtk3_target = target / "gtk-3.0"
    gtk3_target.mkdir(parents=True, exist_ok=True)
    if (gtk3_source / "assets").exists():
        _copytree_clean(gtk3_source / "assets", gtk3_target / "assets")
    subprocess.run(
        [
            "sassc",
            "-I",
            str(gtk3_source),
            str(gtk3_source / "gtk.scss"),
            str(gtk3_target / "gtk.css"),
        ],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    gtk4_target = target / "gtk-4.0"
    gtk4_target.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(gtk3_target / "gtk.css", gtk4_target / "gtk.css")
    except OSError:
        pass
    return str(metadata["gtk_theme"])


def ensure_theme_installed(theme_key: str) -> str:
    THEMES_HOME.mkdir(parents=True, exist_ok=True)
    if theme_key == "retrowave":
        return ensure_retrowave_gtk_theme()
    if theme_key == "dracula":
        return ensure_dracula_gtk_theme()
    return ensure_builtin_hanauta_gtk_theme(theme_key)


def install_qt_color_scheme(theme_name: str, palette: dict[str, str],
                            font_family: str = "Rubik",
                            mono_font_family: str = "JetBrains Mono") -> None:
    colors_conf = _hanauta_qt5ct_colors(palette)
    for cfg_dir in [
        Path.home() / ".config" / "qt5ct" / "colors",
        Path.home() / ".config" / "qt6ct" / "colors",
    ]:
        cfg_dir.mkdir(parents=True, exist_ok=True)
        (cfg_dir / f"{theme_name}.conf").write_text(colors_conf, encoding="utf-8")

    kvantum_dir = Path.home() / ".config" / "Kvantum" / theme_name
    kvantum_dir.mkdir(parents=True, exist_ok=True)
    kvantum_files = _hanauta_kvantum_theme(palette, font_family=font_family,
                                            mono_font_family=mono_font_family)
    for filename, content in kvantum_files.items():
        (kvantum_dir / filename).write_text(content, encoding="utf-8")


def apply_qt_theme(theme_name: str, palette: dict[str, str],
                   icon_theme: str = "Papirus",
                   font_family: str = "Rubik",
                   mono_font_family: str = "JetBrains Mono") -> None:
    install_qt_color_scheme(theme_name, palette, font_family=font_family,
                            mono_font_family=mono_font_family)
    settings_ini = Path.home() / ".config" / "qt5ct" / "qt5ct.conf"
    if settings_ini.exists():
        try:
            import configparser
            cfg = configparser.ConfigParser()
            cfg.read(str(settings_ini))
            if "Appearance" not in cfg:
                cfg["Appearance"] = {}
            cfg["Appearance"]["color_scheme_path"] = str(
                Path.home() / ".config" / "qt5ct" / "colors" / f"{theme_name}.conf"
            )
            cfg["Appearance"]["color_scheme"] = theme_name
            cfg["Appearance"]["icon_theme"] = icon_theme
            cfg["Appearance"]["font"] = f"{font_family},10,-1,5,50,0,0,0,0,0"
            cfg["Appearance"]["monospace_font"] = f"{mono_font_family},10,-1,5,50,0,0,0,0,0"
            with open(settings_ini, "w") as f:
                cfg.write(f)
        except Exception:
            pass

    settings6_ini = Path.home() / ".config" / "qt6ct" / "qt6ct.conf"
    if settings6_ini.exists():
        try:
            import configparser
            cfg = configparser.ConfigParser()
            cfg.read(str(settings6_ini))
            if "Appearance" not in cfg:
                cfg["Appearance"] = {}
            cfg["Appearance"]["color_scheme_path"] = str(
                Path.home() / ".config" / "qt6ct" / "colors" / f"{theme_name}.conf"
            )
            cfg["Appearance"]["color_scheme"] = theme_name
            cfg["Appearance"]["icon_theme"] = icon_theme
            cfg["Appearance"]["font"] = f"{font_family},10,-1,5,50,0,0,0,0,0"
            cfg["Appearance"]["monospace_font"] = f"{mono_font_family},10,-1,5,50,0,0,0,0,0"
            with open(settings6_ini, "w") as f:
                cfg.write(f)
        except Exception:
            pass


def apply_gtk_theme(
    theme_name: str, color_scheme: str = "prefer-dark", icon_theme: str = "",
    palette: dict[str, str] | None = None,
    font_family: str = "Rubik",
    mono_font_family: str = "JetBrains Mono",
) -> None:
    ROOT = Path(__file__).resolve().parents[2].parents[1]
    cmd = ["bash", str(ROOT / "hanauta" / "scripts" / "set_theme.sh"), theme_name]
    if icon_theme:
        cmd.append(icon_theme)
    else:
        cmd.append("")
    cmd.append(color_scheme)
    cmd.append(font_family)
    cmd.append(mono_font_family)
    subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    if palette:
        install_qt_color_scheme(theme_name, palette)


def sync_static_theme_from_settings(
    settings_state: dict, apply_gtk: bool = False
) -> str:
    from settings_page.theme_data import THEME_LIBRARY
    from settings_page.settings_store import _atomic_write_json_file
    from settings_page.settings_store import PYQT_THEME_FILE
    theme_key = selected_theme_key(settings_state)
    metadata = THEME_LIBRARY[theme_key]
    fonts = dict(metadata.get("fonts", HANAUTA_FONT_PROFILE))
    font_family = fonts.get("ui_font_family", "Rubik")
    mono_font_family = fonts.get("mono_font_family", "JetBrains Mono")
    write_pyqt_palette(
        dict(metadata["palette"]),
        use_matugen=False,
        fonts=fonts,
    )
    from settings_page.settings_store import PYQT_THEME_DIR
    PYQT_THEME_DIR.mkdir(parents=True, exist_ok=True)
    if apply_gtk:
        theme_name = ensure_theme_installed(theme_key)
        palette = dict(metadata["palette"])
        icon_theme = str(metadata.get("icon_theme", "Papirus"))
        apply_qt_theme(theme_name, palette, icon_theme=icon_theme,
                       font_family=font_family, mono_font_family=mono_font_family)
        apply_gtk_theme(theme_name, str(metadata.get("color_scheme", "prefer-dark")),
                        icon_theme=icon_theme, palette=palette,
                        font_family=font_family, mono_font_family=mono_font_family)
    return theme_key


def write_pyqt_palette(
    palette: dict[str, str],
    use_matugen: bool = False,
    fonts: dict[str, str] | None = None,
) -> None:
    from settings_page.settings_store import PYQT_THEME_FILE, _atomic_write_json_file
    from settings_page.settings_store import PYQT_THEME_DIR
    PYQT_THEME_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"use_matugen": bool(use_matugen)}
    payload.update(palette)
    if fonts:
        payload.update(fonts)
    _atomic_write_json_file(PYQT_THEME_FILE, payload)


def write_default_pyqt_palette(use_matugen: bool = False) -> None:
    from settings_page.theme_data import HANAUTA_DARK_PALETTE
    write_pyqt_palette(HANAUTA_DARK_PALETTE, use_matugen=use_matugen)
