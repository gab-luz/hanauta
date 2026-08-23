from __future__ import annotations

from pyqt.shared.material_icons import material_icon as _material_icon

# Re-export for backward compatibility
def material_icon(name: str) -> str:
    return _material_icon(name)