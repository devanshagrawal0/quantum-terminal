# MangoTrades / Hyperliquid Terminal — Premium Design Specification

**Goal:** kill the "consumer app" look (rounded corners, glows, neon cyan, gradients, soft shadows, big padding, cartoon charts) and rebuild the dashboard as a **quant-firm-grade 4K trading terminal** — Bloomberg / Refinitiv / elite-desk internal-tool class. Dense, quiet, buildable. Every value below is real and ready to drop into CSS variables.

This spec is derived from the shared design language of pro terminals (Bloomberg, TradingView pro-dark, Hyperliquid, Linear/Vercel-class dark systems), not any one product's proprietary look.

---

## A. Design Principles (the rules)

1. **Earn the dark ground.** The near-black canvas is not decoration — it exists so that *data* is the only thing that emits light. If a pixel isn't data, a label, a hairline, or a state, it should be background. No filler.
2. **One accent, used as punctuation.** A single amber/gold accent marks interaction and selection only (focus ring, active tab, selected row, primary action). Never paint whole panels in the accent. Green/red are reserved strictly for P&L and directional meaning.
3. **Kill the glow.** No `box-shadow` blooms, no neon, no `filter: drop-shadow`, no gradient fills on charts or cards. Depth comes from **1px hairline borders and a 4-step luminance ramp**, exactly like Linear/Vercel — not from shadows.
4. **Radius ≈ 0.** Corners are `2px` max (effectively square). Rounded 12–16px cards read as consumer. Panels are rectangles that tile edge-to-edge.
5. **Tabular numerics everywhere.** Every number uses a monospaced/tabular figure so columns align and live-updating values never jump. Numbers are right-aligned in tables.
6. **Density is the feature, not the bug.** Compact grids, micro-labels, 24–28px rows. Pack maximum information without clutter by using hierarchy (size/weight/color), not whitespace. Whitespace is rationed, not sprayed.
7. **Hierarchy through type + value color, not boxes.** Distinguish sections with weight, uppercase micro-labels, and hairlines — not with 8 differently-colored rounded cards.
8. **Direction is dual-encoded.** P&L up/down is shown by color **and** by sign/arrow (`+`/`−`, `▲`/`▼`), so it survives colorblindness and grayscale printouts. (~8% of men have red/green deficiency.)
9. **Positions are the protagonist.** The open-book blotter gets the largest, top-left-anchored zone. Everything else is context around the book.
10. **Charts are instruments, not illustrations.** Thin 1px–1.5px lines, translucent 6–10% fills, near-invisible gridlines, direct value labels, no legends-as-decoration. A chart must answer a number, not "look cool."
11. **F-pattern placement.** The eye lands top-left and scans right then down. Highest-value info (account P&L, positions, risk state) goes top and left; exploratory/reference data goes lower-right.
12. **Consistency is luxury.** One space scale, one type scale, one border color, one radius. Quiet uniformity is what makes it read as "institutional" rather than "template."

---

## B. Color Tokens (role → exact HEX)

Design token architecture: primitive HEX → semantic role → component. Only semantic tokens below are used in components.

### Backgrounds / Elevations (4-step ramp, ~+5–7% luminance per step)
| Token | HEX | Use |
|---|---|---|
| `--bg-canvas` | `#0A0C10` | App background, the deepest ground (the "black" the data sits on) |
| `--bg-panel` | `#0F1218` | Panels, cards, blotter body, sidebars |
| `--bg-elevated` | `#141821` | Panel headers, nested rows, table header row, popovers |
| `--bg-hover` | `#1A1F2A` | Row hover, active cell, dropdown/overlay, selected-tab body |
| `--bg-inset` | `#080A0D` | Sunken wells (search field, code/thesis box, chart plot area) |

### Borders (hairlines only — never shadows)
| Token | HEX | Use |
|---|---|---|
| `--border-hairline` | `#1C2230` | Default 1px divider between panels, rows, columns |
| `--border-strong` | `#2A3242` | Emphasized separations, panel outer edge, focused input |
| `--border-faint` | `#141a26` | Internal grid lines inside dense tables (barely visible) |

### Text
| Token | HEX | Use |
|---|---|---|
| `--text-primary` | `#E6E9EF` | Primary values, coin symbols, headings (off-white, **never** `#FFFFFF`) |
| `--text-secondary` | `#9AA3B2` | Secondary data, sub-values, axis numbers |
| `--text-muted` | `#5B6472` | Uppercase micro-labels, column headers, helper text, units |
| `--text-disabled` | `#3A4150` | Inactive/placeholder |

### Accent (the single restrained color)
| Token | HEX | Use |
|---|---|---|
| `--accent` | `#E0A63C` | Amber-gold. Active-tab underline, focus ring, selected-row marker, primary button, links, key figures being highlighted |
| `--accent-hover` | `#EDB859` | Hover/active of accent controls |
| `--accent-dim` | `#6A5326` | Accent at ~30% for subtle fills (selected-row left border bg, gauge tracks) |

### Semantic — direction & state
| Token | HEX | Use |
|---|---|---|
| `--pos` | `#34C08A` | Gain / long / risk-on / up (muted green, **not** neon `#00FF88`) |
| `--pos-dim` | `#12291F` | Gain fill background (row tint, chart area fill) |
| `--neg` | `#E2565B` | Loss / short / risk-off / down (muted red) |
| `--neg-dim` | `#2A1416` | Loss fill background |
| `--warn` | `#E8873C` | Caution/alert feed, elevated risk (orange — distinct from gold accent) |
| `--crit` | `#E2565B` | Breaking-point / crash / liquidation-near (reuses neg red) |
| `--info` | `#5B8FF9` | Neutral informational, BTC dominance, hedge legs |
| `--flat` | `#7C8698` | Zero/neutral values, "no change" |

### Chart series (categorical, muted, colorblind-spaced — thin lines)
| # | Token | HEX | Typical use |
|---|---|---|---|
| 1 | `--series-1` | `#E0A63C` | Primary / equity curve / BTC |
| 2 | `--series-2` | `#5B8FF9` | Second series |
| 3 | `--series-3` | `#34C08A` | Positive-leaning series |
| 4 | `--series-4` | `#C77DD8` | Fourth series (violet) |
| 5 | `--series-5` | `#E0865B` | Fifth series (clay) |
| 6 | `--series-6` | `#7C8698` | Reference / benchmark / muted |
| grid | `--chart-grid` | `#161C27` | Gridlines (barely visible) |
| axis | `--chart-axis` | `#5B6472` | Axis labels/ticks |

---

## C. Typography Scale

Two families only: a **tabular mono** for all numerics/data, and a tight **grotesk sans** for labels/prose. Both are on Google Fonts.

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
```

- **Data / numerics / tables / prices / KPIs → `IBM Plex Mono`** (400/500/600/700). Chosen over JetBrains Mono for its calmer, less "codey" letterforms — reads as a Bloomberg-class terminal, not an IDE. Roboto Mono is an acceptable substitute.
- **Labels / headings / thesis text / nav → `Inter`** (400/500/600/700), a tight neutral grotesk. Always enable tabular figures on any Inter number: `font-variant-numeric: tabular-nums;`.
- **Fallback stacks:** `"IBM Plex Mono", "Roboto Mono", ui-monospace, monospace` and `"Inter", -apple-system, "Segoe UI", sans-serif`.

### Type scale (4K-tuned; scale to viewport)
| Token | Size / line-height | Weight | Tracking | Font | Where |
|---|---|---|---|---|---|
| `--t-micro` | 10px / 12px | 600 | `+0.08em` UPPERCASE | Inter | Column headers, micro-labels ("UNREALIZED", "LIQ") |
| `--t-label` | 11px / 14px | 500 | `+0.02em` | Inter | Secondary labels, tags, helper |
| `--t-data-s` | 12px / 16px | 500 | `0` | Plex Mono | Dense table cells, scanner rows |
| `--t-data` | 13px / 18px | 500 | `0` | Plex Mono | Standard data, position rows |
| `--t-data-m` | 15px / 20px | 600 | `0` | Plex Mono | Emphasized figures (mark, entry) |
| `--t-body` | 13px / 19px | 400 | `0` | Inter | Thesis, prose, notes |
| `--t-heading` | 13px / 16px | 600 | `+0.06em` UPPERCASE | Inter | Panel titles |
| `--t-kpi` | 22px / 24px | 600 | `-0.01em` | Plex Mono | Top-ribbon KPI values |
| `--t-kpi-hero` | 30px / 32px | 700 | `-0.02em` | Plex Mono | Total P&L hero figure |

**Rules:** numbers right-aligned + tabular; units (`$`, `%`, `x`, `bps`) in `--text-muted` at one size smaller; panel titles are uppercase micro at `--text-muted`; never use font sizes above 30px anywhere — big type is consumer.

---

## D. Spacing / Density System

Base unit **4px**. Everything is a multiple. Terminals are tight — default to the *smaller* option.

| Token | px | Use |
|---|---|---|
| `--sp-1` | 2 | Icon-to-text, inline gaps |
| `--sp-2` | 4 | Cell inner padding (vertical) |
| `--sp-3` | 6 | Cell inner padding (horizontal), tight stacks |
| `--sp-4` | 8 | Standard element gap, panel inner padding |
| `--sp-5` | 12 | Panel header padding, section gaps |
| `--sp-6` | 16 | Panel-to-panel gap (the *largest* routine gap) |
| `--sp-8` | 24 | Major zone separation only |

| Token | value | Use |
|---|---|---|
| `--row-h-compact` | 24px | Scanner (176 coins), leaders/laggards, dense lists |
| `--row-h` | 28px | Positions blotter rows, standard tables |
| `--row-h-header` | 26px | Table header row |
| `--radius` | 2px | Every corner (buttons, panels, inputs, chips) |
| `--radius-0` | 0px | Tables, blotter, tab strip (fully square) |
| `--border-w` | 1px | All borders. Never thicker than 1px except active-tab underline (2px accent) |
| `--panel-pad` | 12px | Panel content padding (headers 8px 12px) |
| `--grid-gap` | 8px | Gap between panels in the workspace grid |

**Grid:** 16-column CSS Grid workspace, `gap: var(--grid-gap)`. Left nav rail fixed **56px** (icon-only). Panels tile with 1px hairline seams; no floating cards, no drop shadows, no outer margins around panels — they meet the viewport edges.

**Density mandate:** row vertical padding = `4px`; horizontal cell padding = `8px`; a position row shows ~11 columns in 28px height. Header rows are `--bg-elevated` with `--t-micro` uppercase labels.

---

## E. Chart Styling Rules

Global: **no gradients, no glow, no drop-shadow, no rounded bar caps, no 3D, no legends unless >2 series.** Plot area background = `--bg-inset` or transparent. Value readouts are printed as tabular text next to the chart, not just hover tooltips.

### Line chart (equity curve, price)
- Stroke **1.25px**, color `--series-1`. No point markers except the last point (2px dot).
- Gridlines: horizontal only, `--chart-grid` (`#161C27`), 1px — must be barely perceptible. No vertical gridlines.
- Optional area fill: solid `--pos-dim`/`--neg-dim` at **8% opacity max**, flat — never a vertical gradient to transparent.
- Axis labels `--chart-axis`, `--t-data-s`, sparse (4–5 ticks). Last value labeled directly at the line end in `--text-primary`.
- Y-axis does not need to start at zero for P&L; annotate the zero line as a 1px `--border-strong` dashed rule.

### Sparkline (in position rows, scanner)
- 1px line, single color = direction of net change (`--pos`/`--neg`). No axes, no fill, no dots. ~64×20px inside the row. Pure trend shape.

### Heatmap (scanner returns, correlation, funding)
- Discrete cells, **1px `--bg-canvas` gap** between cells (grid look, square). No rounded cells.
- Diverging scale anchored at 0: negatives ramp `--neg-dim → --neg`, positives `--pos-dim → --pos`; near-zero = `--bg-elevated`. Text label inside cell in tabular mono if it fits.
- No smooth blur/interpolation — crisp cells.

### Bars (returns, exposure, breadth)
- Flat fill, square corners, `--series-*` or semantic. 1px `--bg-canvas` gap between bars. Baseline at 0 drawn as `--border-strong`.
- Horizontal bars for ranked lists (leaders/laggards). Value printed at bar end in tabular mono. No gradient, no shadow.

### Donut / gauge (regime, TIDE, RISK, ROTATION scores)
- **Thin ring, 3–4px stroke**, square line-cap ends. Track = `--accent-dim`/`#1C2230`; value arc = semantic color for the score. Center holds the number (`--t-kpi`, tabular) + micro-label. No fat 40px donuts, no drop shadow, no gradient sweep.
- Prefer **linear segmented meters** (5–7 ticks) over donuts for risk scores — reads more instrument-like.

**Institutional vs kiddish cheat-sheet:** thin > thick; muted > saturated; translucent flat fill > gradient; direct label > floating legend; 1px grid > bold grid; square > rounded; one accent > rainbow.

---

## F. Layout Blueprint (positions-first, globe centerpiece)

16-col grid. Left **nav rail 56px**. Then three working columns: **A = Positions (primary, widest)**, **B = Market-State centerpiece with the 3D globe**, **C = Cross-sectional context**. A slim **global KPI ribbon** spans the top; a **caution/alert ticker** pins the bottom.

Rationale: F-pattern puts the account state (top ribbon) and the open book (column A, top-left) where the eye lands. The globe is the visual centerpiece dead-center (column B) surrounded by the market-brain gauges — it's the "hero" without stealing the book's dominance. Reference/exploratory data (leaders, scanner, scorecard) sits lower-right where scanning attention decays.

### Zone map
- **Top ribbon (full width, 64px):** account KPIs — Total P&L (hero), Realized, Unrealized, Win-rate, Fees, Net Exposure, Open Count. Tabular, dual-encoded, hairline-separated cells.
- **Nav rail (56px, left):** icon-only workspace switcher + status LED (WS connected, hedge active).
- **Column A — POSITIONS (≈7/16, primary):** the blotter. Dense 28px rows: `Coin · Side/Lev · Entry · Mark · Liq · uPnL$ · uPnL% · Funding · Tag · Spark`. Row expands to reveal thesis. This is the biggest single panel on screen.
- **Column B — MARKET STATE (≈5/16, center):** the **3D WebGL globe** as centerpiece, with the **Regime** label overlaid beneath it (label + why), flanked by four compact gauges: **TIDE** (risk-on/off score), **RISK** (breaking-point/crash), **ROTATION** (stage/tilt), and breadth/funding-positive fraction. Below the globe: the **equity curve** line chart.
- **Column C — CROSS-SECTION (≈4/16, right):** stacked panels — **Leaders/Laggards** (beat-the-tide, residual strength), **BTC Hedge** state, **Forward Scorecard** (hit-rate, edge/pick), and a compact **Scanner** launcher/top-movers. Full 176-coin scanner opens as its own workspace tab.
- **Bottom ticker (full width, 28px):** conditional-order triggers + caution/alert feed, scrolling, `--warn`/`--crit` coded.

### ASCII wireframe

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ ▓ TOTAL P&L +$12,480 ▲2.1% │ REAL +$8.2k │ UNREAL +$4.3k │ WIN 61% │ FEES $412 │ EXP 3.4x │ OPEN 7 │  ← KPI ribbon 64px
├──┬───────────────────────────────────────────┬──────────────────────────┬───────────────┤
│  │ POSITIONS  (open book — PRIMARY)           │ MARKET STATE             │ LEADERS / LAG │
│N │ COIN SIDE/LEV ENTRY  MARK   LIQ   uPnL$ uPnL%│    ╭──────────╮          │ SOL  +4.2 ▲   │
│A │ ─────────────────────────────────────────── │    │   ◍ 3D    │          │ INJ  +3.8 ▲   │
│V │ BTC  L 5x  62,140 63,020  54k  +880  +1.4 ⌁ │    │  GLOBE    │          │ ─────────────  │
│  │ ETH  L 3x   3,180  3,244  2.6k +192 +2.0 ⌁ │    ╰──────────╯          │ ARB  -2.9 ▼   │
│56│ SOL  L 8x    138.2  145.9  120  +61  +5.5 ⌁ │  REGIME: Risk-On Alt    │ OP   -3.4 ▼   │
│px│ WIF  S 4x     2.41   2.28  3.1  +0.5 +5.3 ⌁ │  ┌TIDE┐┌RISK┐┌ROTN┐     ├───────────────┤
│  │ ...thesis expands on row click...          │  │+0.62││ L3 ││Early│     │ BTC HEDGE     │
│  │ ─────────────────────────────────────────── │  └────┘└────┘└────┘     │ Active 82% cov│
│  │                                             │  Breadth 58%  Fund +71% │ uPnL +$140    │
│  │                                             │ ┌─────────────────────┐ ├───────────────┤
│  │                                             │ │   EQUITY CURVE  ╱‾   │ │ SCORECARD     │
│  │                                             │ │             ╱‾      │ │ Hit 64% Edge+1.2│
│  │                                             │ └─────────────────────┘ │ SCANNER ▸176   │
├──┴───────────────────────────────────────────┴──────────────────────────┴───────────────┤
│ ⚠ TRIG: ETH TP 3,300 armed  ·  CAUTION: funding flip on WIF  ·  RISK L3 breaking-point ▲  │  ← ticker 28px
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

All seams are 1px `--border-hairline`. Panels have no radius, no shadow, no outer margin — they tile.

---

## G. Tab / Navigation Design

The current tabs "don't work" — replace with a **two-level model**:

1. **Left icon rail (56px, always visible):** top-level *workspaces*, one glyph each, no text. Active workspace marked by a **2px `--accent` left-edge bar** + `--text-primary` icon; inactive icons `--text-muted`. Keyboard `1`–`9` jumps workspaces (Bloomberg-style command speed). Rail bottom holds live status LEDs (WS, hedge, data-age).
   - Workspaces: **Cockpit** (the F-layout above, default), **Scanner** (full 176-coin grid), **Leaders**, **Hedge**, **Scorecard/Journal**, **Settings**.
2. **In-panel tab strips (where a panel needs modes):** flat text tabs, **underline-active** (`2px --accent` under the active label), uppercase `--t-micro`, `--text-muted` inactive → `--text-primary` active. **No pills, no rounded backgrounds, no filled tab chips.** Tabs sit on the panel header's hairline. Example: Positions panel tabs `OPEN · CLOSED · ALL`; Market-State tabs `REGIME · TIDE · RISK · ROTATION`.

Why it works: the icon rail is persistent and instant (no hunting), in-panel tabs stay local to their data (no global tab soup), and the flat underline style reads as a terminal, not a browser.

Interaction states (all controls): default `--text-secondary`; hover `--bg-hover` + `--text-primary`; active/selected `--accent` marker; focus `1px --accent` ring inset (no glow). Everything keyboard-navigable.

---

## H. "What to Display Where" — prioritized

Ranked by importance; placement follows F-pattern (top/left = highest).

1. **Total account P&L (+ day change)** — top ribbon, far left, hero figure. First thing the eye hits.
2. **Open positions blotter** — Column A, the dominant panel. uPnL$/% dual-encoded, liq price flagged `--crit` when mark is within N% of liq.
3. **Realized / Unrealized / Net Exposure / Open count / Win-rate / Fees** — rest of top ribbon, hairline-separated.
4. **Regime label + why** — Column B under the globe (the "so what" of the whole market).
5. **RISK (breaking-point / crash score)** — Column B gauge, escalates to bottom ticker in `--crit` when high. Risk must be impossible to miss.
6. **TIDE (macro risk-on/off) + ROTATION (stage/tilt)** — Column B gauges beside RISK.
7. **Equity curve** — Column B lower, confirms the P&L trend at a glance.
8. **Leaders / Laggards (beat-the-tide, residual strength)** — Column C top; the actionable cross-section.
9. **BTC hedge state (coverage %, legs, pnl)** — Column C; risk-posture context.
10. **Forward scorecard (hit-rate, edge/pick)** — Column C; are the picks working.
11. **Conditional triggers + caution/alert feed** — bottom ticker, always visible, `--warn`/`--crit`.
12. **Full 176-coin scanner (1D/7D/30D, funding, basis)** — its own workspace tab (too big for the cockpit; a top-movers summary lives in Column C).

---

## I. Concrete Before → After (10 changes)

1. **Corners:** `border-radius: 12–16px` → **`2px`** everywhere (tables/tabs `0`). Cards become panels.
2. **Depth:** remove every `box-shadow`/glow/`drop-shadow` → depth from the **4-step bg ramp + 1px hairlines** (`--border-hairline #1C2230`).
3. **Accent:** neon cyan `#00E0FF`-style everywhere → **single amber `#E0A63C`**, used only for active/selected/focus/primary. Panels go monochrome.
4. **P&L colors:** neon green/red (`#00FF88`/`#FF3B3B`) → **muted `#34C08A` / `#E2565B`**, and add `+/−`/`▲▼` so it's dual-encoded.
5. **Backgrounds:** flat dark-navy or `#1E1E2E` gradient panels → **`--bg-canvas #0A0C10` + `--bg-panel #0F1218`** flat, gradient-free.
6. **Text:** pure white `#FFFFFF` body → **off-white `#E6E9EF`**, with a real 3-tier hierarchy (`#9AA3B2` / `#5B6472`).
7. **Numbers:** proportional sans figures that wobble on update → **IBM Plex Mono, tabular, right-aligned**; units demoted to muted.
8. **Density:** 44–56px rows with big padding → **28px rows, 4/8px padding**; show ~11 position columns without scroll.
9. **Charts:** gradient-filled glowing area charts with fat lines & bold grids → **1.25px lines, ≤8% flat fills, `#161C27` hairline grid, direct end-labels, no legend**.
10. **Tabs:** rounded filled pill tabs that break → **56px icon rail (keyboard 1–9) + flat underline in-panel tabs**; active = 2px amber underline, no pill.

---

### Implementation quick-start (CSS variables)
```css
:root{
  --bg-canvas:#0A0C10; --bg-panel:#0F1218; --bg-elevated:#141821; --bg-hover:#1A1F2A; --bg-inset:#080A0D;
  --border-hairline:#1C2230; --border-strong:#2A3242; --border-faint:#141A26;
  --text-primary:#E6E9EF; --text-secondary:#9AA3B2; --text-muted:#5B6472; --text-disabled:#3A4150;
  --accent:#E0A63C; --accent-hover:#EDB859; --accent-dim:#6A5326;
  --pos:#34C08A; --pos-dim:#12291F; --neg:#E2565B; --neg-dim:#2A1416;
  --warn:#E8873C; --crit:#E2565B; --info:#5B8FF9; --flat:#7C8698;
  --series-1:#E0A63C; --series-2:#5B8FF9; --series-3:#34C08A; --series-4:#C77DD8; --series-5:#E0865B; --series-6:#7C8698;
  --chart-grid:#161C27; --chart-axis:#5B6472;
  --radius:2px; --border-w:1px; --grid-gap:8px; --row-h:28px; --panel-pad:12px;
  --font-mono:"IBM Plex Mono","Roboto Mono",ui-monospace,monospace;
  --font-sans:"Inter",-apple-system,"Segoe UI",sans-serif;
}
*{ box-shadow:none !important; } /* enforce during migration */
.num{ font-family:var(--font-mono); font-variant-numeric:tabular-nums; text-align:right; }
```

---

**Sources (research basis):** Bloomberg UX (color accessibility, concealing complexity), Linear/Vercel dark token systems, TradingView pro-dark chart conventions, Hyperliquid interface deep-dive, ColorArchive financial-UI color guide, AG Grid compactness spec, dashboard F-pattern/IA research.
