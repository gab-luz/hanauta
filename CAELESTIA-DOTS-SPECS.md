# CAELESTIA-DOTS-SPECS

## Purpose

Reference notes for styling Hanauta's Life Organizer using patterns observed in the Caelestia dotfiles project.

## Sources

- GitHub README: https://github.com/caelestia-dots/shell
- DeepWiki overview: https://deepwiki.com/caelestia-dots/shell
- DeepWiki design system notes: https://deepwiki.com/caelestia-dots/shell/6.3-styling-and-material-design

## High-Level Style Direction

- Strong Material Design 3 Expressive influence.
- Rounded, soft, glassy surfaces instead of flat rectangular cards.
- Layered panels with translucency and blur-like atmosphere.
- Large spacing, clear grouping, and gentle contrast transitions.
- UI prioritizes calm readability over dense information packing.

## Color System

- Dynamic color pipeline built around wallpaper-derived palettes.
- Material You style roles are used rather than ad-hoc colors:
  - `primary`
  - `secondary`
  - `surface`
  - `surfaceContainer`
  - `outline`
  - `onSurface`
- Surfaces are often translucent and stacked with borders instead of hard shadows alone.
- Accent is usually reserved for focus, active state, chips, and strong call-to-action moments.

## Typography

- Primary UI font: `Rubik`
- Icon system: `Material Symbols Rounded`
- Typical hierarchy from the Caelestia styling docs:
  - Labels/meta: around `11px`
  - Standard content: around `12px`
  - Section emphasis: around `14px`
  - Cards/headlines: around `17px`
  - Large hero numbers or display moments: around `25px`
- General feeling:
  - medium-to-bold titles
  - restrained body text
  - compact meta copy
  - expressive but not oversized display moments

## Shape Language

- Default corners are very rounded.
- Frequent radius values mentioned in the design system:
  - `17px`
  - `18px`
  - `19px`
  - `20px`
  - `25px`
- Larger containers tend to use higher radii than small chips/buttons.
- Buttons and nav items feel pill-like rather than flat tabs.

## Spacing And Layout

- Common spacing values in the design notes:
  - `8px`
  - `12px`
  - `16px`
  - `18px`
  - `20px`
  - `25px`
- Layout favors:
  - generous padding inside cards
  - moderate gaps between content groups
  - clear left-to-right scan structure
- Positioning is balanced and centered visually even when aligned left structurally.

## Material 3 Expressive Patterns Observed

- Large hero area with one key upcoming/focus action.
- Support metrics arranged in secondary cards beneath the hero.
- Navigation chips use active/focused containers rather than only text-color changes.
- Cards combine:
  - translucent surface
  - subtle outline
  - high radius
  - selective accent glow or gradient
- Active states rely on container fill plus border change, not only hover tint.

## Interaction Guidance

- Motion should feel soft and short, not springy or flashy.
- Expand/collapse interactions should avoid sudden jumps.
- Hover affordances are visible but subtle.
- Compact mode should preserve icon recognition first, labels second.

## Practical Styling Rules For Hanauta

- Keep `Rubik` for UI copy and `Material Symbols Rounded` or `Material Icons` for icons.
- Use `13px` nav titles and `11px` nav subtitles.
- Use white or near-white iconography when sidebar surfaces are dark and translucent.
- Prefer nav chips with visible filled containers, not transparent rows.
- Keep card radii in the `18px` to `28px` range.
- Use hero surfaces with gradient blends between `primaryContainer`, `secondary`, and elevated surface colors.
- Restrict pure accent color to active state, slider handles, badges, and selected chips.
- In compact layouts, switch to fewer columns before text becomes cramped.

## What We Reused In Life Organizer

- Rounded pill-style sidebar navigation.
- High-radius, layered cards.
- Dynamic palette friendliness for Matugen and custom accents.
- Clear 11/13/19/25 size hierarchy.
- MD3-style hero plus supporting metric cards.

## Crypto Widget Notes

- Keep the existing crypto information architecture:
  - coin selector
  - hero summary for the selected asset
  - spot price
  - 24h move
  - chart window
  - line/area chart
  - status copy
- Prefer a "market pulse" composition instead of a utilitarian dashboard.
- Hero card should feel atmospheric:
  - soft diagonal gradient
  - translucent glass base
  - one badge row with small metadata
  - oversized current price
  - short momentum sentence
- Secondary metrics should live in three equally weighted glass cards under the hero.
- Charts should be framed inside their own elevated card, not dropped directly on the panel background.
- Use subtle grid lines and a low-opacity area fill beneath the line to echo Caelestia's layered shell panels.
- Positive/negative change should affect accent treatment:
  - positive can lean toward `primary`
  - negative can lean toward `error`
  - avoid saturated neon red/green blocks
- Status text should sit in a muted pill or soft card so operational feedback feels integrated with the shell.
- Preferred widget sizing for this family:
  - width around `580px`
  - height around `720px` to `760px`
- In future Hanauta widgets using this spec:
  - start with one expressive hero
  - move supporting facts into small cards
  - treat charts, feeds, or logs as separate glass surfaces
  - keep typography calm and rounded rather than compact-terminal dense
