const fs = require("fs");
const os = require("os");
const path = require("path");
const vscode = require("vscode");

const DEFAULT_PALETTE_PATH = "~/.local/state/hanauta/theme/pyqt_palette.json";
const THEME_SCHEMA_VERSION = 3;
let activeContext = null;

const WORKBENCH_KEYS = [
  "editor.background",
  "editor.foreground",
  "editorLineNumber.foreground",
  "editorLineNumber.activeForeground",
  "editorLineNumber.dimmedForeground",
  "editorCursor.foreground",
  "editorGutter.background",
  "editor.selectionBackground",
  "editor.inactiveSelectionBackground",
  "editor.selectionHighlightBackground",
  "editor.selectionHighlightBorder",
  "editor.wordHighlightBackground",
  "editor.wordHighlightStrongBackground",
  "editor.wordHighlightBorder",
  "editor.wordHighlightStrongBorder",
  "editor.findMatchBackground",
  "editor.findMatchForeground",
  "editor.findMatchHighlightBackground",
  "editor.findMatchBorder",
  "editor.findMatchHighlightBorder",
  "editorHoverWidget.background",
  "editorHoverWidget.foreground",
  "editorHoverWidget.border",
  "editorHoverWidget.statusBarBackground",
  "editorSuggestWidget.background",
  "editorSuggestWidget.foreground",
  "editorSuggestWidget.selectedBackground",
  "editorSuggestWidget.selectedForeground",
  "editorSuggestWidget.highlightForeground",
  "editorSuggestWidget.focusHighlightForeground",
  "editorWidget.background",
  "editorWidget.foreground",
  "editorWidget.border",
  "editorWidget.resizeBorder",
  "editorGroupHeader.tabsBackground",
  "editorGroupHeader.tabsBorder",
  "editorGroupHeader.border",
  "editorGroup.border",
  "tab.activeBackground",
  "tab.activeForeground",
  "tab.activeBorder",
  "tab.activeBorderTop",
  "tab.inactiveBackground",
  "tab.inactiveForeground",
  "tab.unfocusedActiveBackground",
  "tab.unfocusedActiveForeground",
  "tab.unfocusedInactiveBackground",
  "tab.unfocusedInactiveForeground",
  "tab.hoverBackground",
  "tab.hoverForeground",
  "tab.border",
  "sideBar.background",
  "sideBar.foreground",
  "sideBar.border",
  "sideBar.dropBackground",
  "sideBarTitle.foreground",
  "sideBarTitle.background",
  "sideBarTitle.border",
  "sideBarSectionHeader.background",
  "sideBarSectionHeader.foreground",
  "sideBarSectionHeader.border",
  "sideBarActivityBarTop.border",
  "sideBarStickyScroll.background",
  "sideBarStickyScroll.border",
  "sideBarStickyScroll.shadow",
  "activityBar.background",
  "activityBar.foreground",
  "activityBar.inactiveForeground",
  "activityBar.activeBackground",
  "activityBar.activeBorder",
  "activityBar.activeFocusBorder",
  "activityBarBadge.background",
  "activityBarBadge.foreground",
  "activityBar.border",
  "activityBarTop.background",
  "activityBarTop.foreground",
  "activityBarTop.inactiveForeground",
  "activityBarTop.activeBackground",
  "activityBarTop.activeBorder",
  "activityWarningBadge.background",
  "activityWarningBadge.foreground",
  "activityErrorBadge.background",
  "activityErrorBadge.foreground",
  "profileBadge.background",
  "profileBadge.foreground",
  "titleBar.activeBackground",
  "titleBar.activeForeground",
  "titleBar.inactiveBackground",
  "titleBar.inactiveForeground",
  "titleBar.border",
  "commandCenter.background",
  "commandCenter.foreground",
  "commandCenter.border",
  "commandCenter.inactiveForeground",
  "commandCenter.activeBackground",
  "commandCenter.activeForeground",
  "commandCenter.activeBorder",
  "statusBar.background",
  "statusBar.foreground",
  "statusBar.border",
  "statusBar.focusBorder",
  "statusBarItem.activeBackground",
  "statusBarItem.hoverForeground",
  "statusBarItem.hoverBackground",
  "statusBarItem.focusBorder",
  "statusBarItem.prominentForeground",
  "statusBarItem.prominentBackground",
  "panel.background",
  "panel.border",
  "panel.dropBorder",
  "panelTitle.activeForeground",
  "panelTitle.activeBorder",
  "panelTitle.inactiveForeground",
  "panelTitle.border",
  "panelTitleBadge.background",
  "panelTitleBadge.foreground",
  "panelInput.border",
  "panelSection.border",
  "panelSection.dropBackground",
  "panelSectionHeader.background",
  "panelSectionHeader.foreground",
  "panelSectionHeader.border",
  "panelStickyScroll.background",
  "panelStickyScroll.border",
  "panelStickyScroll.shadow",
  "button.background",
  "button.foreground",
  "button.border",
  "button.hoverBackground",
  "button.secondaryForeground",
  "button.secondaryBackground",
  "button.secondaryHoverBackground",
  "button.secondaryBorder",
  "input.background",
  "input.foreground",
  "input.border",
  "input.placeholderForeground",
  "inputOption.activeBackground",
  "inputOption.activeBorder",
  "inputOption.activeForeground",
  "inputOption.hoverBackground",
  "inputValidation.errorBackground",
  "inputValidation.errorForeground",
  "inputValidation.errorBorder",
  "inputValidation.infoBackground",
  "inputValidation.infoForeground",
  "inputValidation.infoBorder",
  "inputValidation.warningBackground",
  "inputValidation.warningForeground",
  "inputValidation.warningBorder",
  "dropdown.background",
  "dropdown.foreground",
  "dropdown.border",
  "dropdown.listBackground",
  "checkbox.background",
  "checkbox.foreground",
  "checkbox.border",
  "list.activeSelectionBackground",
  "list.activeSelectionForeground",
  "list.hoverBackground",
  "list.hoverForeground",
  "list.inactiveSelectionBackground",
  "list.inactiveSelectionForeground",
  "list.inactiveSelectionIconForeground",
  "list.focusBackground",
  "list.focusForeground",
  "list.focusOutline",
  "list.focusAndSelectionOutline",
  "list.inactiveFocusBackground",
  "list.inactiveFocusOutline",
  "list.dropBackground",
  "list.dropBetweenBackground",
  "list.highlightForeground",
  "list.focusHighlightForeground",
  "list.deemphasizedForeground",
  "list.errorForeground",
  "list.warningForeground",
  "listFilterWidget.background",
  "listFilterWidget.outline",
  "listFilterWidget.noMatchesOutline",
  "listFilterWidget.shadow",
  "list.filterMatchBackground",
  "list.filterMatchBorder",
  "tree.indentGuidesStroke",
  "tree.inactiveIndentGuidesStroke",
  "focusBorder",
  "contrastBorder",
  "foreground",
  "disabledForeground",
  "textLink.foreground",
  "textLink.activeForeground",
  "badge.background",
  "badge.foreground",
  "descriptionForeground",
  "icon.foreground",
  "toolbar.hoverBackground",
  "toolbar.activeBackground",
  "menu.background",
  "menu.foreground",
  "menu.selectionBackground",
  "menu.selectionForeground",
  "menu.selectionBorder",
  "menu.separatorBackground",
  "menu.border",
  "menubar.selectionForeground",
  "menubar.selectionBackground",
  "menubar.selectionBorder",
  "quickInput.background",
  "quickInput.foreground",
  "quickInputTitle.background",
  "pickerGroup.foreground",
  "pickerGroup.border",
  "settings.headerForeground",
  "settings.headerBorder",
  "settings.modifiedItemIndicator",
  "settings.settingsHeaderHoverForeground",
  "settings.dropdownBackground",
  "settings.dropdownForeground",
  "settings.dropdownBorder",
  "settings.dropdownListBorder",
  "settings.checkboxBackground",
  "settings.checkboxForeground",
  "settings.checkboxBorder",
  "settings.rowHoverBackground",
  "settings.focusedRowBackground",
  "settings.focusedRowBorder",
  "settings.textInputBackground",
  "settings.textInputForeground",
  "settings.textInputBorder",
  "settings.numberInputBackground",
  "settings.numberInputForeground",
  "settings.numberInputBorder",
  "settings.sashBorder",
  "terminal.background",
  "terminal.foreground",
  "terminalCursor.foreground",
  "terminal.ansiBlue",
  "terminal.ansiCyan",
  "terminal.ansiGreen",
  "terminal.ansiMagenta",
  "terminal.ansiRed",
  "terminal.ansiYellow"
];

function expandHome(filePath) {
  if (!filePath || filePath === "~") {
    return os.homedir();
  }
  if (filePath.startsWith("~/")) {
    return path.join(os.homedir(), filePath.slice(2));
  }
  return filePath;
}

function normalizeHex(color, fallback) {
  let value = String(color || "").trim();
  if (!value.startsWith("#")) {
    value = `#${value}`;
  }
  if (!/^#[0-9a-fA-F]{6}$/.test(value)) {
    return fallback;
  }
  return value.toUpperCase();
}

function hexToRgb(color) {
  const value = normalizeHex(color, "#000000");
  return {
    r: parseInt(value.slice(1, 3), 16),
    g: parseInt(value.slice(3, 5), 16),
    b: parseInt(value.slice(5, 7), 16)
  };
}

function rgba(color, alpha) {
  const { r, g, b } = hexToRgb(color);
  const clamped = Math.max(0, Math.min(1, alpha));
  return `rgba(${r}, ${g}, ${b}, ${clamped.toFixed(2)})`;
}

function blend(colorA, colorB, ratio) {
  const a = hexToRgb(colorA);
  const b = hexToRgb(colorB);
  const t = Math.max(0, Math.min(1, ratio));
  const r = Math.round(a.r + (b.r - a.r) * t);
  const g = Math.round(a.g + (b.g - a.g) * t);
  const bValue = Math.round(a.b + (b.b - a.b) * t);
  return `#${r.toString(16).padStart(2, "0")}${g.toString(16).padStart(2, "0")}${bValue.toString(16).padStart(2, "0")}`.toUpperCase();
}

function relativeLuminance(color) {
  const { r, g, b } = hexToRgb(color);
  const channel = (value) => {
    const normalized = value / 255;
    if (normalized <= 0.03928) {
      return normalized / 12.92;
    }
    return Math.pow((normalized + 0.055) / 1.055, 2.4);
  };
  return (0.2126 * channel(r)) + (0.7152 * channel(g)) + (0.0722 * channel(b));
}

function pickForeground(background, preferred, fallback) {
  const bg = relativeLuminance(background);
  const preferredLum = relativeLuminance(preferred);
  const fallbackLum = relativeLuminance(fallback);
  const preferredContrast = (Math.max(bg, preferredLum) + 0.05) / (Math.min(bg, preferredLum) + 0.05);
  const fallbackContrast = (Math.max(bg, fallbackLum) + 0.05) / (Math.min(bg, fallbackLum) + 0.05);
  return preferredContrast >= fallbackContrast ? preferred : fallback;
}

function buildPalette(raw) {
  const defaults = {
    primary: "#D0BCFF",
    on_primary: "#381E72",
    primary_container: "#4F378B",
    on_primary_container: "#EADDFF",
    secondary: "#CCC2DC",
    on_secondary: "#332D41",
    tertiary: "#EFB8C8",
    on_tertiary: "#492532",
    background: "#141218",
    on_background: "#E6E0E9",
    surface: "#141218",
    on_surface: "#E6E0E9",
    surface_container: "#211F26",
    surface_container_high: "#2B2930",
    surface_variant: "#49454F",
    on_surface_variant: "#CAC4D0",
    outline: "#938F99",
    error: "#F2B8B5",
    on_error: "#601410"
  };

  const palette = { ...defaults, ...(raw || {}) };
  for (const key of Object.keys(defaults)) {
    palette[key] = normalizeHex(palette[key], defaults[key]);
  }

  return {
    ...palette,
    text: pickForeground(palette.surface_container_high, palette.on_surface, "#FFFFFF"),
    textMuted: rgba(pickForeground(palette.surface_container_high, palette.on_surface_variant, palette.on_surface), 0.76),
    activeText: pickForeground(palette.primary, palette.on_primary, "#101114"),
    backgroundSoft: rgba(palette.surface_container, 0.96),
    backgroundRaised: rgba(palette.surface_container_high, 0.98),
    border: rgba(palette.outline, 0.28),
    borderSoft: rgba(palette.outline, 0.18),
    hover: rgba(palette.primary, 0.14),
    selection: rgba(palette.primary, 0.24),
    selectionStrong: rgba(palette.primary, 0.34),
    inactive: rgba(palette.on_surface_variant, 0.66),
    terminalBlue: blend(palette.primary, "#7AB8FF", 0.42),
    terminalCyan: blend(palette.secondary, "#6EE7F0", 0.45),
    terminalGreen: blend(palette.tertiary, "#7DFFB1", 0.35),
    terminalMagenta: blend(palette.primary, palette.tertiary, 0.45),
    terminalRed: palette.error,
    terminalYellow: blend(palette.primary, "#FFD36A", 0.65)
  };
}

function buildWorkbenchColors(palette) {
  const hoverStrong = rgba(palette.primary, 0.18);
  const selectionSoft = rgba(palette.primary, 0.16);
  const selectionBorder = rgba(palette.primary, 0.42);
  const errorSoft = rgba(palette.error, 0.18);
  const warningBase = blend(palette.terminalYellow, palette.primary, 0.22);
  const warningSoft = rgba(warningBase, 0.18);
  const infoBase = blend(palette.primary, palette.secondary, 0.22);
  const infoSoft = rgba(infoBase, 0.18);

  return {
    "editor.background": palette.background,
    "editor.foreground": palette.text,
    "editorLineNumber.foreground": rgba(palette.primary, 0.82),
    "editorLineNumber.activeForeground": palette.primary,
    "editorLineNumber.dimmedForeground": rgba(palette.on_surface_variant, 0.44),
    "editorCursor.foreground": palette.primary,
    "editorGutter.background": palette.background,
    "editor.selectionBackground": palette.selection,
    "editor.inactiveSelectionBackground": selectionSoft,
    "editor.selectionHighlightBackground": rgba(palette.primary, 0.16),
    "editor.selectionHighlightBorder": selectionBorder,
    "editor.wordHighlightBackground": rgba(palette.secondary, 0.14),
    "editor.wordHighlightStrongBackground": rgba(palette.primary, 0.18),
    "editor.wordHighlightBorder": rgba(palette.secondary, 0.32),
    "editor.wordHighlightStrongBorder": selectionBorder,
    "editor.findMatchBackground": rgba(palette.tertiary, 0.26),
    "editor.findMatchForeground": pickForeground(blend(palette.tertiary, palette.background, 0.36), palette.text, "#101114"),
    "editor.findMatchHighlightBackground": rgba(palette.tertiary, 0.14),
    "editor.findMatchBorder": rgba(palette.tertiary, 0.42),
    "editor.findMatchHighlightBorder": rgba(palette.tertiary, 0.26),
    "editorHoverWidget.background": palette.backgroundRaised,
    "editorHoverWidget.foreground": palette.text,
    "editorHoverWidget.border": palette.border,
    "editorHoverWidget.statusBarBackground": rgba(palette.surface_variant, 0.42),
    "editorSuggestWidget.background": palette.backgroundRaised,
    "editorSuggestWidget.foreground": palette.text,
    "editorSuggestWidget.selectedBackground": palette.hover,
    "editorSuggestWidget.selectedForeground": palette.text,
    "editorSuggestWidget.highlightForeground": palette.primary,
    "editorSuggestWidget.focusHighlightForeground": palette.primary,
    "editorWidget.background": palette.backgroundRaised,
    "editorWidget.foreground": palette.text,
    "editorWidget.border": palette.border,
    "editorWidget.resizeBorder": palette.primary,
    "editorGroupHeader.tabsBackground": palette.backgroundSoft,
    "editorGroupHeader.tabsBorder": palette.borderSoft,
    "editorGroupHeader.border": palette.borderSoft,
    "editorGroup.border": palette.borderSoft,
    "tab.activeBackground": palette.surface_container_high,
    "tab.activeForeground": palette.text,
    "tab.activeBorder": palette.primary,
    "tab.activeBorderTop": palette.primary,
    "tab.inactiveBackground": palette.surface_container,
    "tab.inactiveForeground": palette.textMuted,
    "tab.unfocusedActiveBackground": rgba(palette.surface_container_high, 0.94),
    "tab.unfocusedActiveForeground": palette.textMuted,
    "tab.unfocusedInactiveBackground": rgba(palette.surface_container, 0.88),
    "tab.unfocusedInactiveForeground": rgba(palette.on_surface_variant, 0.54),
    "tab.hoverBackground": hoverStrong,
    "tab.hoverForeground": palette.text,
    "tab.border": palette.borderSoft,
    "sideBar.background": palette.surface_container,
    "sideBar.foreground": palette.text,
    "sideBar.border": palette.borderSoft,
    "sideBar.dropBackground": rgba(palette.primary, 0.20),
    "sideBarTitle.foreground": palette.primary,
    "sideBarTitle.background": palette.surface_container_high,
    "sideBarTitle.border": palette.borderSoft,
    "sideBarSectionHeader.background": rgba(palette.surface_variant, 0.34),
    "sideBarSectionHeader.foreground": palette.text,
    "sideBarSectionHeader.border": palette.borderSoft,
    "sideBarActivityBarTop.border": palette.borderSoft,
    "sideBarStickyScroll.background": palette.surface_container_high,
    "sideBarStickyScroll.border": palette.borderSoft,
    "sideBarStickyScroll.shadow": rgba(palette.background, 0.34),
    "activityBar.background": palette.surface_container_high,
    "activityBar.foreground": palette.primary,
    "activityBar.inactiveForeground": palette.inactive,
    "activityBar.activeBackground": rgba(palette.primary, 0.14),
    "activityBar.activeBorder": palette.primary,
    "activityBar.activeFocusBorder": blend(palette.primary, "#FFFFFF", 0.20),
    "activityBarBadge.background": palette.primary,
    "activityBarBadge.foreground": palette.activeText,
    "activityBar.border": palette.borderSoft,
    "activityBarTop.background": palette.surface_container_high,
    "activityBarTop.foreground": palette.primary,
    "activityBarTop.inactiveForeground": palette.inactive,
    "activityBarTop.activeBackground": rgba(palette.primary, 0.14),
    "activityBarTop.activeBorder": palette.primary,
    "activityWarningBadge.background": warningBase,
    "activityWarningBadge.foreground": pickForeground(warningBase, "#101114", palette.text),
    "activityErrorBadge.background": palette.error,
    "activityErrorBadge.foreground": pickForeground(palette.error, "#101114", palette.text),
    "profileBadge.background": palette.secondary,
    "profileBadge.foreground": pickForeground(palette.secondary, "#101114", palette.text),
    "titleBar.activeBackground": palette.surface_container_high,
    "titleBar.activeForeground": palette.text,
    "titleBar.inactiveBackground": palette.surface_container,
    "titleBar.inactiveForeground": palette.textMuted,
    "titleBar.border": palette.borderSoft,
    "commandCenter.background": palette.backgroundRaised,
    "commandCenter.foreground": palette.text,
    "commandCenter.border": palette.border,
    "commandCenter.inactiveForeground": palette.textMuted,
    "commandCenter.activeBackground": hoverStrong,
    "commandCenter.activeForeground": palette.text,
    "commandCenter.activeBorder": palette.primary,
    "statusBar.background": palette.surface_container_high,
    "statusBar.foreground": palette.text,
    "statusBar.border": palette.borderSoft,
    "statusBar.focusBorder": palette.primary,
    "statusBarItem.activeBackground": hoverStrong,
    "statusBarItem.hoverForeground": palette.text,
    "statusBarItem.hoverBackground": palette.hover,
    "statusBarItem.focusBorder": palette.primary,
    "statusBarItem.prominentForeground": palette.text,
    "statusBarItem.prominentBackground": rgba(palette.primary, 0.18),
    "panel.background": palette.surface_container,
    "panel.border": palette.borderSoft,
    "panel.dropBorder": palette.primary,
    "panelTitle.activeForeground": palette.primary,
    "panelTitle.activeBorder": palette.primary,
    "panelTitle.inactiveForeground": palette.textMuted,
    "panelTitle.border": palette.borderSoft,
    "panelTitleBadge.background": palette.primary,
    "panelTitleBadge.foreground": palette.activeText,
    "panelInput.border": palette.border,
    "panelSection.border": palette.borderSoft,
    "panelSection.dropBackground": rgba(palette.primary, 0.20),
    "panelSectionHeader.background": rgba(palette.surface_variant, 0.34),
    "panelSectionHeader.foreground": palette.text,
    "panelSectionHeader.border": palette.borderSoft,
    "panelStickyScroll.background": palette.surface_container_high,
    "panelStickyScroll.border": palette.borderSoft,
    "panelStickyScroll.shadow": rgba(palette.background, 0.34),
    "button.background": palette.primary,
    "button.foreground": palette.activeText,
    "button.border": rgba(palette.primary, 0.26),
    "button.hoverBackground": blend(palette.primary, "#FFFFFF", 0.12),
    "button.secondaryForeground": palette.text,
    "button.secondaryBackground": rgba(palette.surface_variant, 0.44),
    "button.secondaryHoverBackground": rgba(palette.surface_variant, 0.58),
    "button.secondaryBorder": palette.borderSoft,
    "input.background": palette.backgroundRaised,
    "input.foreground": palette.text,
    "input.border": palette.border,
    "input.placeholderForeground": palette.textMuted,
    "inputOption.activeBackground": rgba(palette.primary, 0.18),
    "inputOption.activeBorder": palette.primary,
    "inputOption.activeForeground": palette.text,
    "inputOption.hoverBackground": hoverStrong,
    "inputValidation.errorBackground": errorSoft,
    "inputValidation.errorForeground": palette.text,
    "inputValidation.errorBorder": rgba(palette.error, 0.44),
    "inputValidation.infoBackground": infoSoft,
    "inputValidation.infoForeground": palette.text,
    "inputValidation.infoBorder": rgba(infoBase, 0.44),
    "inputValidation.warningBackground": warningSoft,
    "inputValidation.warningForeground": palette.text,
    "inputValidation.warningBorder": rgba(warningBase, 0.44),
    "dropdown.background": palette.backgroundRaised,
    "dropdown.foreground": palette.text,
    "dropdown.border": palette.border,
    "dropdown.listBackground": palette.backgroundRaised,
    "checkbox.background": palette.backgroundRaised,
    "checkbox.foreground": palette.primary,
    "checkbox.border": palette.border,
    "list.activeSelectionBackground": palette.selection,
    "list.activeSelectionForeground": palette.text,
    "list.focusBackground": palette.selectionStrong,
    "list.focusForeground": palette.text,
    "list.focusOutline": palette.primary,
    "list.focusAndSelectionOutline": palette.primary,
    "list.hoverBackground": palette.hover,
    "list.hoverForeground": palette.text,
    "list.inactiveSelectionBackground": rgba(palette.primary, 0.16),
    "list.inactiveSelectionForeground": palette.text,
    "list.inactiveSelectionIconForeground": palette.primary,
    "list.inactiveFocusBackground": rgba(palette.primary, 0.12),
    "list.inactiveFocusOutline": rgba(palette.primary, 0.30),
    "list.dropBackground": rgba(palette.primary, 0.22),
    "list.dropBetweenBackground": palette.primary,
    "list.highlightForeground": palette.primary,
    "list.focusHighlightForeground": palette.primary,
    "list.deemphasizedForeground": palette.textMuted,
    "list.errorForeground": palette.error,
    "list.warningForeground": warningBase,
    "listFilterWidget.background": palette.backgroundRaised,
    "listFilterWidget.outline": palette.primary,
    "listFilterWidget.noMatchesOutline": rgba(palette.error, 0.44),
    "listFilterWidget.shadow": rgba(palette.background, 0.28),
    "list.filterMatchBackground": rgba(palette.primary, 0.14),
    "list.filterMatchBorder": rgba(palette.primary, 0.24),
    "tree.indentGuidesStroke": palette.borderSoft,
    "tree.inactiveIndentGuidesStroke": rgba(palette.outline, 0.12),
    "focusBorder": palette.primary,
    "contrastBorder": palette.borderSoft,
    "foreground": palette.text,
    "disabledForeground": palette.inactive,
    "textLink.foreground": palette.primary,
    "textLink.activeForeground": blend(palette.primary, "#FFFFFF", 0.14),
    "badge.background": palette.primary,
    "badge.foreground": palette.activeText,
    "descriptionForeground": palette.textMuted,
    "icon.foreground": palette.text,
    "toolbar.hoverBackground": hoverStrong,
    "toolbar.activeBackground": rgba(palette.primary, 0.22),
    "menu.background": palette.backgroundRaised,
    "menu.foreground": palette.text,
    "menu.selectionBackground": palette.hover,
    "menu.selectionForeground": palette.text,
    "menu.selectionBorder": palette.primary,
    "menu.separatorBackground": palette.borderSoft,
    "menu.border": palette.border,
    "menubar.selectionForeground": palette.text,
    "menubar.selectionBackground": hoverStrong,
    "menubar.selectionBorder": palette.primary,
    "quickInput.background": palette.backgroundRaised,
    "quickInput.foreground": palette.text,
    "quickInputTitle.background": palette.surface_container_high,
    "pickerGroup.foreground": palette.primary,
    "pickerGroup.border": palette.borderSoft,
    "settings.headerForeground": palette.primary,
    "settings.headerBorder": palette.borderSoft,
    "settings.modifiedItemIndicator": palette.primary,
    "settings.settingsHeaderHoverForeground": blend(palette.primary, "#FFFFFF", 0.16),
    "settings.dropdownBackground": palette.backgroundRaised,
    "settings.dropdownForeground": palette.text,
    "settings.dropdownBorder": palette.border,
    "settings.dropdownListBorder": palette.borderSoft,
    "settings.checkboxBackground": palette.backgroundRaised,
    "settings.checkboxForeground": palette.primary,
    "settings.checkboxBorder": palette.border,
    "settings.rowHoverBackground": hoverStrong,
    "settings.focusedRowBackground": selectionSoft,
    "settings.focusedRowBorder": palette.primary,
    "settings.textInputBackground": palette.backgroundRaised,
    "settings.textInputForeground": palette.text,
    "settings.textInputBorder": palette.border,
    "settings.numberInputBackground": palette.backgroundRaised,
    "settings.numberInputForeground": palette.text,
    "settings.numberInputBorder": palette.border,
    "settings.sashBorder": palette.borderSoft,
    "terminal.background": palette.background,
    "terminal.foreground": palette.text,
    "terminalCursor.foreground": palette.primary,
    "terminal.ansiBlue": palette.terminalBlue,
    "terminal.ansiCyan": palette.terminalCyan,
    "terminal.ansiGreen": palette.terminalGreen,
    "terminal.ansiMagenta": palette.terminalMagenta,
    "terminal.ansiRed": palette.terminalRed,
    "terminal.ansiYellow": palette.terminalYellow
  };
}

function buildTokenColors(palette) {
  return {
    textMateRules: [
      {
        scope: ["comment", "punctuation.definition.comment"],
        settings: { foreground: palette.textMuted }
      },
      {
        scope: ["string", "string.quoted"],
        settings: { foreground: palette.secondary }
      },
      {
        scope: ["constant", "constant.numeric", "constant.language"],
        settings: { foreground: palette.tertiary }
      },
      {
        scope: ["keyword", "storage", "storage.type"],
        settings: { foreground: palette.primary }
      },
      {
        scope: ["entity.name.function", "support.function", "meta.function-call"],
        settings: { foreground: blend(palette.primary, palette.secondary, 0.35) }
      },
      {
        scope: ["entity.name.type", "support.type", "entity.name.class"],
        settings: { foreground: blend(palette.tertiary, palette.secondary, 0.40) }
      },
      {
        scope: ["variable", "meta.definition.variable"],
        settings: { foreground: palette.text }
      }
    ]
  };
}

function buildSemanticTokenColors(palette) {
  return {
    enabled: true,
    rules: {
      variable: palette.text,
      property: palette.secondary,
      parameter: blend(palette.secondary, palette.text, 0.25),
      function: blend(palette.primary, palette.secondary, 0.35),
      method: blend(palette.primary, palette.secondary, 0.35),
      class: blend(palette.tertiary, palette.secondary, 0.40),
      interface: blend(palette.tertiary, palette.secondary, 0.55),
      enum: palette.tertiary,
      keyword: palette.primary,
      string: palette.secondary,
      number: palette.tertiary,
      comment: palette.textMuted
    }
  };
}

async function mergeOwnedKeys(settingName, ownedKeys, nextValues) {
  const configuration = vscode.workspace.getConfiguration();
  const current = configuration.get(settingName, {});
  const merged = { ...(current || {}) };
  for (const key of ownedKeys) {
    delete merged[key];
  }
  for (const [key, value] of Object.entries(nextValues)) {
    merged[key] = value;
  }
  await configuration.update(settingName, merged, vscode.ConfigurationTarget.Global);
}

async function clearOwnedKeys(settingName, ownedKeys) {
  const configuration = vscode.workspace.getConfiguration();
  const current = configuration.get(settingName, {});
  const merged = { ...(current || {}) };
  for (const key of ownedKeys) {
    delete merged[key];
  }
  await configuration.update(settingName, merged, vscode.ConfigurationTarget.Global);
}

async function updateFullSetting(settingName, nextValue) {
  const configuration = vscode.workspace.getConfiguration();
  await configuration.update(settingName, nextValue, vscode.ConfigurationTarget.Global);
}

function readPaletteFile(filePath) {
  const raw = fs.readFileSync(filePath, "utf8");
  return JSON.parse(raw);
}

async function applyPaletteFromFile(filePath, context) {
  const rawPalette = readPaletteFile(filePath);
  if (!rawPalette || rawPalette.use_matugen === false) {
    await restoreEditorSettings(context);
    await clearOwnedKeys("workbench.colorCustomizations", WORKBENCH_KEYS);
    await context.globalState.update("hanautaTheme.lastSignature", "");
    return;
  }
  const palette = buildPalette(rawPalette);
  const applyEditorTokens = vscode.workspace.getConfiguration("hanautaTheme").get("applyEditorTokens", false);
  const signature = JSON.stringify(palette);
  const signatureWithMode = `${THEME_SCHEMA_VERSION}:${signature}:${applyEditorTokens ? "tokens" : "workbench"}`;
  const previousSignature = context.globalState.get("hanautaTheme.lastSignature", "");
  if (signatureWithMode === previousSignature) {
    return;
  }

  await mergeOwnedKeys("workbench.colorCustomizations", WORKBENCH_KEYS, buildWorkbenchColors(palette));
  if (applyEditorTokens) {
    await backupEditorSettings(context);
    await updateFullSetting("editor.tokenColorCustomizations", buildTokenColors(palette));
    await updateFullSetting("editor.semanticTokenColorCustomizations", buildSemanticTokenColors(palette));
  } else {
    await restoreEditorSettings(context);
  }
  await context.globalState.update("hanautaTheme.lastSignature", signatureWithMode);
}

async function clearManagedThemeState(context) {
  if (!context) {
    return;
  }
  await restoreEditorSettings(context);
  await clearOwnedKeys("workbench.colorCustomizations", WORKBENCH_KEYS);
  await context.globalState.update("hanautaTheme.lastSignature", "");
}

function createPaletteWatcher(filePath, callback) {
  const directory = path.dirname(filePath);
  const filename = path.basename(filePath);

  if (!fs.existsSync(directory)) {
    fs.mkdirSync(directory, { recursive: true });
  }

  const watcher = fs.watch(directory, { persistent: false }, (_eventType, changedName) => {
    if (!changedName || changedName !== filename) {
      return;
    }
    callback();
  });

  fs.watchFile(filePath, { interval: 1200 }, () => {
    callback();
  });

  return {
    dispose() {
      watcher.close();
      fs.unwatchFile(filePath);
    }
  };
}

function scheduleApply(filePath, context) {
  let timer = null;
  return () => {
    if (timer) {
      clearTimeout(timer);
    }
    timer = setTimeout(async () => {
      timer = null;
      try {
        await applyPaletteFromFile(filePath, context);
      } catch (error) {
        console.error("[hanauta-theme] failed applying palette", error);
      }
    }, 180);
  };
}

function resolvePaletteFile() {
  const configuration = vscode.workspace.getConfiguration("hanautaTheme");
  const configuredPath = configuration.get("paletteFile", DEFAULT_PALETTE_PATH);
  return expandHome(configuredPath);
}

function isAutoApplyEnabled() {
  return vscode.workspace.getConfiguration("hanautaTheme").get("autoApply", true);
}

function looksLikeManagedTokenColors(value) {
  if (!value || typeof value !== "object" || !Array.isArray(value.textMateRules)) {
    return false;
  }
  const scopes = value.textMateRules
    .flatMap((rule) => Array.isArray(rule.scope) ? rule.scope : [])
    .map((scope) => String(scope));
  return scopes.includes("comment") && scopes.includes("string") && scopes.includes("keyword");
}

function looksLikeManagedSemanticColors(value) {
  if (!value || typeof value !== "object" || typeof value.rules !== "object") {
    return false;
  }
  const keys = Object.keys(value.rules || {});
  return keys.includes("variable") && keys.includes("function") && keys.includes("keyword");
}

async function backupEditorSettings(context) {
  const configuration = vscode.workspace.getConfiguration();
  if (!context.globalState.get("hanautaTheme.backup.tokenSaved", false)) {
    await context.globalState.update(
      "hanautaTheme.backup.tokenColorCustomizations",
      configuration.get("editor.tokenColorCustomizations", null)
    );
    await context.globalState.update("hanautaTheme.backup.tokenSaved", true);
  }
  if (!context.globalState.get("hanautaTheme.backup.semanticSaved", false)) {
    await context.globalState.update(
      "hanautaTheme.backup.semanticTokenColorCustomizations",
      configuration.get("editor.semanticTokenColorCustomizations", null)
    );
    await context.globalState.update("hanautaTheme.backup.semanticSaved", true);
  }
}

async function restoreEditorSettings(context) {
  const configuration = vscode.workspace.getConfiguration();
  const currentToken = configuration.get("editor.tokenColorCustomizations", null);
  const currentSemantic = configuration.get("editor.semanticTokenColorCustomizations", null);
  if (context.globalState.get("hanautaTheme.backup.tokenSaved", false)) {
    await configuration.update(
      "editor.tokenColorCustomizations",
      context.globalState.get("hanautaTheme.backup.tokenColorCustomizations", {}),
      vscode.ConfigurationTarget.Global
    );
    await context.globalState.update("hanautaTheme.backup.tokenSaved", false);
  } else if (looksLikeManagedTokenColors(currentToken)) {
    await configuration.update("editor.tokenColorCustomizations", {}, vscode.ConfigurationTarget.Global);
  }
  if (context.globalState.get("hanautaTheme.backup.semanticSaved", false)) {
    await configuration.update(
      "editor.semanticTokenColorCustomizations",
      context.globalState.get("hanautaTheme.backup.semanticTokenColorCustomizations", {}),
      vscode.ConfigurationTarget.Global
    );
    await context.globalState.update("hanautaTheme.backup.semanticSaved", false);
  } else if (looksLikeManagedSemanticColors(currentSemantic)) {
    await configuration.update("editor.semanticTokenColorCustomizations", {}, vscode.ConfigurationTarget.Global);
  }
}

async function activate(context) {
  activeContext = context;
  let paletteFile = resolvePaletteFile();
  let applySoon = scheduleApply(paletteFile, context);
  let watcher = createPaletteWatcher(paletteFile, () => {
    if (isAutoApplyEnabled()) {
      applySoon();
    }
  });

  context.subscriptions.push(
    watcher,
    vscode.commands.registerCommand("hanautaTheme.refreshNow", async () => {
      paletteFile = resolvePaletteFile();
      applySoon = scheduleApply(paletteFile, context);
      await applyPaletteFromFile(paletteFile, context);
      vscode.window.setStatusBarMessage("Hanauta wallpaper theme refreshed", 2000);
    }),
    vscode.commands.registerCommand("hanautaTheme.restoreDefaults", async () => {
      await clearManagedThemeState(context);
      vscode.window.setStatusBarMessage("Hanauta editor theme customizations removed", 2500);
    }),
    vscode.workspace.onDidChangeConfiguration(async (event) => {
      if (!event.affectsConfiguration("hanautaTheme.paletteFile") && !event.affectsConfiguration("hanautaTheme.applyEditorTokens")) {
        return;
      }
      watcher.dispose();
      paletteFile = resolvePaletteFile();
      applySoon = scheduleApply(paletteFile, context);
      watcher = createPaletteWatcher(paletteFile, () => {
        if (isAutoApplyEnabled()) {
          applySoon();
        }
      });
      context.subscriptions.push(watcher);
      if (fs.existsSync(paletteFile) && isAutoApplyEnabled()) {
        await applyPaletteFromFile(paletteFile, context);
      }
    })
  );

  if (fs.existsSync(paletteFile) && isAutoApplyEnabled()) {
    await applyPaletteFromFile(paletteFile, context);
  }
}

async function deactivate() {
  if (!activeContext) {
    return;
  }
  try {
    await clearManagedThemeState(activeContext);
  } catch (error) {
    console.error("[hanauta-theme] failed to clean up on deactivate", error);
  }
}

module.exports = {
  activate,
  deactivate
};
