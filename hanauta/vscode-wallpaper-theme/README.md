# Hanauta Wallpaper Theme

This extension watches Hanauta's shared palette file:

- `~/.local/state/hanauta/theme/pyqt_palette.json`

When the wallpaper palette changes, it updates:

- `workbench.colorCustomizations`
- `editor.tokenColorCustomizations`
- `editor.semanticTokenColorCustomizations`

The extension only owns the keys it writes into `workbench.colorCustomizations`.
Other unrelated workbench color customizations are preserved.

Command:

- `Hanauta: Refresh Wallpaper Theme`
