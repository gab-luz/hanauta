import subprocess
from pathlib import Path
from PyQt6.QtGui import QFont, QFontDatabase

from settings_page.settings_store import _atomic_write_json_file
from settings_page.theme_data import HANAUTA_FONT_PROFILE


APP_DIR = Path(__file__).resolve().parents[2]
ROOT = APP_DIR.parents[1]
FONTS_DIR = ROOT / "assets" / "fonts"


def load_app_fonts() -> dict[str, str]:
    loaded: dict[str, str] = {}
    font_map = {
        "material_icons": FONTS_DIR / "MaterialIcons-Regular.ttf",
        "material_icons_outlined": FONTS_DIR / "MaterialIconsOutlined-Regular.otf",
        "material_symbols_rounded": FONTS_DIR / "MaterialSymbolsRounded.ttf",
        "ui_sans": FONTS_DIR / "GoogleSans-Regular.ttf",
        "ui_sans_medium": FONTS_DIR / "GoogleSans-Medium.ttf",
        "ui_display": FONTS_DIR / "GoogleSansDisplay-Regular.ttf",
        "ui_display_medium": FONTS_DIR / "GoogleSansDisplay-Medium.ttf",
    }
    for key, path in font_map.items():
        if not path.exists():
            continue
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id < 0:
            continue
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            loaded[key] = families[0]
    return loaded


def detect_font(*families: str) -> str:
    for family in families:
        if family and QFont(family).exactMatch():
            return family
    return "Sans Serif"


def _is_rubik_font(font_name: str) -> bool:
    return "rubik" in (font_name or "").strip().lower()


def _button_qfont_weight(font_name: str) -> QFont.Weight:
    return QFont.Weight.Medium if _is_rubik_font(font_name) else QFont.Weight.DemiBold


def _button_css_weight(font_name: str) -> int:
    return 500 if _is_rubik_font(font_name) else 600


def apply_antialias_font(widget) -> None:
    from PyQt6.QtWidgets import QWidget
    font = widget.font()
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    widget.setFont(font)
    for child in widget.findChildren(QWidget):
        child_font = child.font()
        child_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        child.setFont(child_font)