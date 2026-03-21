# Design System Document

## 1. Overview & Creative North Star

### Creative North Star: "The Obsidian Nexus"
This design system is a high-fidelity tribute to the elite Linux desktop aesthetic. It moves beyond the "web-app" feel, adopting the precision of a tiled window manager (Hyprland) fused with the warmth of modern editorial design. It is built on three pillars: **Obsidian Depth, Kinetic Glow, and Intentional Asymmetry.**

By utilizing deep, bluish-purple foundations and vibrant Hanauta accents, the system feels alive—as if it is a glowing terminal interface projected onto a sheet of dark glass. We reject the "flat" movement in favor of **Tonal Layering**, where hierarchy is defined by the physical behavior of light and depth rather than structural lines.

---

## 2. Colors

The palette is anchored in the "Hanauta" color story: a deep, nocturnal base contrasted with soft, bioluminescent accents.

### The "No-Line" Rule
**Explicit Instruction:** Traditional 1px solid borders are strictly prohibited for sectioning. Boundaries must be defined solely through background color shifts. Use `surface-container-low` (#1a1b26) for sections sitting on the base `surface` (#12131d). This creates a "molded" look rather than a "pasted" look.

### Surface Hierarchy & Nesting
Treat the UI as a series of physical layers:
- **Base Layer:** `surface` (#12131d) or `surface-dim`.
- **Primary Containers:** `surface-container-low` (#1a1b26).
- **Nested Objects:** `surface-container-high` (#282935) or `surface-container-highest` (#333440).
This "nesting" creates natural focus. An input field or a card should always sit one tier higher than its parent container to feel tactile.

### The "Glass & Gradient" Rule
Floating elements (Modals, Tooltips, Dropdowns) must utilize Glassmorphism:
- **Background:** `primary-container` at 15-20% opacity.
- **Backdrop Blur:** 12px to 24px.
- **Signature Gradient:** For high-impact CTAs, use a subtle linear gradient from `primary` (#d4bbff) to `primary-container` (#bb9af7) at 135 degrees.

---

## 3. Typography

The typography strategy balances the geometric rigor of **Lexend** for headlines with the functional clarity of **Inter** for data and body content.

*   **Display & Headlines (Lexend):** Used for "Editorial" moments. Its semi-bold weights convey a premium, customized OS feel.
*   **Body & Labels (Inter):** High legibility. We use slightly increased letter spacing (0.02em) for `label-md` and `label-sm` to mimic the clean look of terminal status bars (Waybar/Polybar).

**Hierarchy through Weight:** 
Instead of drastically changing font sizes, prioritize weight shifts. Use `title-md` in Semi-Bold for section headers to maintain a compact, "pro" desktop density.

---

## 4. Elevation & Depth

### The Layering Principle
Forget shadows for static elements. Elevation is achieved through **Tonal Stacking**.
*   **In-set feel:** `surface-container-lowest` (#0c0d18) creates an etched-in, recessed look for secondary inputs or background panels.
*   **Lifted feel:** `surface-container-highest` (#333440) provides a soft, natural lift.

### Ambient Shadows
For floating components (like a music player or system dialogue), use a "Material You" inspired glow:
- **Shadow 1:** Large, diffused blur (40px-60px), 5% opacity, colored with `primary` (#d4bbff).
- **Shadow 2:** Tight, inner "rim light" using a `ghost-border` to define the edge.

### The "Ghost Border" Fallback
If contrast requires a boundary, use the `outline-variant` (#4a4550) at **10% opacity**. This creates a suggestion of a border that reacts to the background, maintaining the "glass" illusion.

---

## 5. Components

### Buttons
*   **Primary:** High-saturation `primary` (#d4bbff) with `on-primary` (#3d1b72) text. Roundedness: `full` (pill shape).
*   **Secondary/Outline:** Use the `Ghost Border` (15% opacity `outline-variant`). No solid background.
*   **Interaction:** On hover, apply a `surface-tint` glow at 8% opacity.

### Input Fields
*   **Structure:** No bottom line. Use a `surface-container-high` background with `md` (1.5rem) rounded corners.
*   **State:** Focused states should trigger a 1px `primary` glow, subtly illuminating the surrounding container.

### Cards & Panels
*   **Corner Radius:** Consistently use `lg` (2rem/24px) for parent cards. 
*   **No Dividers:** Separate list items within cards using `spacing-4` (1.4rem) of vertical whitespace or a subtle background shift to `surface-container-highest`.

### Toggles & Sliders
*   **Toggles:** The "track" should be `surface-container-highest`. The "thumb" should be `primary` for the active state.
*   **Sliders:** Use thick tracks (0.5rem) with `primary` fills, mimicking the Material You "thick bar" aesthetic seen in premium desktop environments.

### Custom Component: The "Bento" Status Chip
For system metrics (CPU, Wi-Fi, Battery), use small, pill-shaped chips with `surface-container-low` backgrounds and `primary` icons. These should be clustered in the top-right of panels to reinforce the "Linux Desktop" UX.

---

## 6. Do's and Don'ts

### Do:
*   **Use 24px (lg) corners** for almost everything. It is the signature of this design system.
*   **Embrace negative space.** Let components "breathe" using the `spacing-8` (2.75rem) token between major layout blocks.
*   **Layer intentionally.** Always ask: "Is this element sitting on top of or inside this container?" and pick your `surface-container` token accordingly.

### Don't:
*   **Don't use pure black.** Always use the obsidian-purple `surface` (#12131d) to keep the "Hanauta" soul alive.
*   **Don't use 100% opaque borders.** They break the immersion of the frosted glass effect.
*   **Don't over-shadow.** Reserve shadows for elements that are truly temporary or floating (Popovers, Tooltips). Use tonal shifts for everything else.