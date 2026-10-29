# Reach — Visual Design System & Tokens (DESIGN.md)

This document establishes the official design system, visual tokens, typography, and component standards for Reach. All UI modifications must align with these tokens and rules.

---

## 1. Color Palette & Semantic Tokens

Reach uses a dark-first, high-contrast palette optimized for developer and automation workstations.

### Background Surfaces
| Token | Hex / Value | Usage |
| :--- | :--- | :--- |
| `--bg-body` | `#090d16` | Root document viewport background |
| `--bg-nav` | `rgba(13, 18, 30, 0.85)` | Glassmorphism topbar and navigation backdrop |
| `--bg-surface` | `#131b2e` | Main content panels, sidebars, drawer panels |
| `--bg-surface-hover` | `#1b2640` | Hover states on interactive table rows, list items |
| `--bg-card` | `#182238` | Metric cards, candidate detail cards, modal dialogue bodies |
| `--bg-input` | `#0c1220` | Form inputs, search fields, textareas, terminal logs |

### Borders & Dividers
| Token | Hex / Value | Usage |
| :--- | :--- | :--- |
| `--border-subtle` | `rgba(255, 255, 255, 0.07)` | Card outlines, table row dividers, subtle dividers |
| `--border-medium` | `rgba(255, 255, 255, 0.12)` | Section dividers, sidebar boundaries, interactive elements |
| `--border-focus` | `#6366f1` | Active focus rings, selected tabs, focused inputs |

### Text & Content
| Token | Hex / Value | Usage | Contrast vs `#090d16` |
| :--- | :--- | :--- | :--- |
| `--text-main` | `#f8fafc` | Primary headings, titles, core body text | > 15:1 (WCAG AAA) |
| `--text-dim` | `#94a3b8` | Secondary labels, descriptions, timestamps | > 7:1 (WCAG AAA) |
| `--text-muted` | `#64748b` | Placeholders, inactive icons, subtle hints | > 4.5:1 (WCAG AA) |

### Accent & Status Indicators
| Token | Hex / Value | Semantic Role |
| :--- | :--- | :--- |
| `--accent-indigo` | `#6366f1` | Primary brand accent, active buttons, main indicators |
| `--accent-indigo-hover`| `#4f46e5` | Button hover state |
| `--accent-cyan` | `#06b6d4` | Easy Apply badges, crawler progress indicators |
| `--accent-emerald` | `#10b981` | Sent status, ready state, healthy service status |
| `--accent-amber` | `#f59e0b` | Review state, warnings, rate limit cooldowns |
| `--accent-rose` | `#f43f5e` | Cancelled, unsuitable posts, error logs, scam flags |

---

## 2. Typography

Reach employs three complementary typefaces:

1. **Logo & Wordmark (`--font-logo`)**: `'Space Grotesk', sans-serif`
   - Geometric, modern tech brand identity.
2. **User Interface (`--font-sans`)**: `'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif`
   - High legibility across small UI labels, table columns, and data cards.
3. **Monospace & Code (`--font-mono`)**: `'JetBrains Mono', monospace`
   - Task logs, terminal feeds, job IDs, code snippets, timestamps.

### Typographic Hierarchy
- **Display / App Title**: 20px / font-weight 700
- **Section Headers (H2)**: 16px / font-weight 600 / tracking -0.01em
- **Body & Labels**: 13px–14px / font-weight 400 or 500
- **Sub-labels & Badges**: 11px–12px / font-weight 500 or 600 / uppercase where appropriate

---

## 3. Elevation & Radii

### Border Radii
- `--radius-xs`: `4px` (small badges, tag pills)
- `--radius-sm`: `8px` (buttons, input fields, dropdown menus)
- `--radius-md`: `12px` (cards, modal body sections, task queue items)
- `--radius-lg`: `16px` (modal containers, major layout cards)

### Shadows
- `--shadow-sm`: `0 2px 8px rgba(0, 0, 0, 0.25)`
- `--shadow-md`: `0 8px 24px rgba(0, 0, 0, 0.4)`
- `--shadow-lg`: `0 16px 40px rgba(0, 0, 0, 0.6)`

---

## 4. UI Patterns & Craft Directives

1. **Stationary 100vh App Shell**: The viewport is locked at `100vh` without outer page bounce. Only interior content panels scroll.
2. **Collapsible Sidebar**:
   - Collapsed: `68px` width (icon-only, unsquashed 44x44px touch targets).
   - Expanded: `270px` width (full labels, diagnostic counters).
   - Layout transitions smoothly without content jumps.
3. **Pinned Modals**:
   - Modals use `max-height: calc(100vh - 3rem)` with fixed headers, fixed footers, and scrollable body sections.
4. **No Gratuitous AI Slop**:
   - Never use arbitrary purple-to-pink multi-stop gradients.
   - Do not wrap individual list rows in heavy cards with redundant drop shadows; use clean tabular rows and typographic hierarchy.
5. **Accessibility**:
   - All interactive controls have visible `:focus-visible` rings (`--border-focus`).
   - Contrast standards strictly enforced to WCAG AA minimum.
