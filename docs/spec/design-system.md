# OpenTroop Design Style Specification

> A living document defining the visual language for OpenTroop's web application.
> Current stack: Next.js 15, Tailwind v4, shadcn/ui, Clerk auth, Lucide icons.

---

## 1. Brand Identity & Personality

OpenTroop is a **modern, trustworthy, and community-focused** troop management platform. It should feel like a well-designed consumer product — not enterprise software. The aesthetic should evoke:

- **Outdoors & adventure** — earthy warmth balanced with crisp modernity
- **Reliability** — clear hierarchy, predictable navigation, calm color palette
- **Approachability** — friendly to non-technical troop leaders and parents

### Positioning

| Feels Like | Does NOT Feel Like |
|---|---|
| Linear, Notion, Vercel dashboard | TroopWebHost, legacy portals |
| Premium SaaS app | Government form software |
| Modern nonprofit platform | Generic Bootstrap template |

---

## 2. Color System

### Primary Palette: Slate + Amber

A **warm slate** (desaturated blue-gray with slight warmth) paired with an **amber accent** that pops
as the active/highlight color. Slate conveys reliability and professionalism; amber adds warmth and
references scouting campfire imagery.

```css
/* Warm slate neutrals — hue 250, low chroma with slight warmth */
--slate-50:  oklch(0.985 0.004 250);
--slate-100: oklch(0.960 0.007 250);
--slate-200: oklch(0.912 0.010 250);
--slate-300: oklch(0.840 0.013 250);
--slate-400: oklch(0.720 0.016 250);
--slate-500: oklch(0.580 0.018 250);
--slate-600: oklch(0.460 0.018 250);
--slate-700: oklch(0.360 0.016 250);   /* primary action */
--slate-800: oklch(0.265 0.012 250);
--slate-900: oklch(0.185 0.008 250);
--slate-950: oklch(0.130 0.006 250);

/* Amber accent */
--amber-100: oklch(0.950 0.060 80);
--amber-200: oklch(0.900 0.100 78);
--amber-300: oklch(0.840 0.140 75);
--amber-400: oklch(0.780 0.165 72);
--amber-500: oklch(0.720 0.175 68);   /* sidebar active / highlight */
--amber-600: oklch(0.640 0.170 65);
--amber-700: oklch(0.540 0.155 63);
```

### Semantic Tokens

| Token | Light Mode | Dark Mode |
|---|---|---|
| `--background` | `--slate-50` | `--slate-950` |
| `--foreground` | `--slate-900` | `--slate-100` |
| `--primary` | `--slate-700` | `--slate-200` |
| `--muted` | `--slate-100` | `--slate-800` |
| `--accent` | `--amber-100` | amber/20% |
| `--accent-foreground` | `--amber-700` | `--amber-300` |
| `--border` | `--slate-200` | white/10% |
| `--ring` | `--amber-400` | `--amber-500` |

### Sidebar Tokens (always dark, both modes)

```css
--sidebar:               var(--slate-900);
--sidebar-foreground:    var(--slate-200);
--sidebar-primary:       var(--amber-400);   /* active highlight */
--sidebar-primary-foreground: var(--slate-950);
--sidebar-accent:        var(--slate-800);   /* hover state */
--sidebar-border:        oklch(1 0 0 / 8%);
```

### Dark Mode

The app fully responds to `prefers-color-scheme` — both light and dark system preferences are
supported. The `.dark` CSS class is also supported for future manual toggle. The sidebar stays
dark regardless of color scheme.

### Status / Semantic Badge Colors

All badge styles use **soft tinted** backgrounds — avoid heavy solid-color badges in data-dense views.

| Context | Background | Text | Border |
|---|---|---|---|
| Scout (member type) | `bg-slate-100` | `text-slate-700` | `border-slate-200` |
| Adult (member type) | `bg-amber-50` | `text-amber-700` | `border-amber-200` |
| Active (status) | `bg-green-50` | `text-green-700` | `border-green-200` |
| Inactive (status) | `bg-slate-100` | `text-slate-500` | `border-slate-200` |
| Alumni (status) | `bg-purple-50` | `text-purple-700` | `border-purple-200` |
| Patrol (group type) | `bg-slate-100` | `text-slate-700` | `border-slate-200` |
| Manual (group type) | `bg-amber-50` | `text-amber-700` | `border-amber-200` |
| Dynamic (group type) | `bg-purple-50` | `text-purple-700` | `border-purple-200` |
| System (group) | `bg-slate-100` | `text-slate-500` | `border-slate-200` |

---

## 3. Typography

### Font: **Inter** (primary) + **Geist Mono** (code)

Inter has superior legibility in data-dense UIs, wider Unicode support, and outstanding rendering
across DPI ranges. It is the gold standard for modern SaaS dashboards (Linear, Vercel, Notion).

```ts
// apps/web/src/app/layout.tsx
import { Inter, Geist_Mono } from "next/font/google"

const inter = Inter({
  variable: "--font-sans",
  subsets: ["latin"],
  display: "swap",
})
```

### Type Scale

| Token | Size | Weight | Line Height | Use |
|---|---|---|---|---|
| `text-xs` | 11px | 400/500 | 1.5 | Table metadata, timestamps, badge labels |
| `text-sm` | 13px | 400/500 | 1.5 | Body text, labels, table data |
| `text-base` | 15px | 400 | 1.6 | Sheet body, form text, page header title |
| `text-lg` | 18px | 600 | 1.3 | Section headings |
| `text-xl` | 22px | 600 | 1.2 | Page titles (mobile) |
| `text-2xl` | 26px | 700 | 1.15 | Page titles |
| `text-3xl+` | — | — | — | Reserved for marketing/landing |

### Letter Spacing

- Headings: `tracking-tight` (−0.015em)
- Body: `tracking-normal`
- Column headers / section labels: `text-xs font-semibold uppercase tracking-wide text-muted-foreground`

---

## 4. Sidebar Navigation

### Architecture

Uses shadcn/ui's `Sidebar` component with `collapsible="icon"` — the collapsed state shows icons
only with tooltips on hover.

| State | Width | Shows |
|---|---|---|
| **Expanded** | 220px | App logo + name, icon + label for each nav item, user avatar + "Account" |
| **Collapsed** | 56px | Compact "OT" logo mark, icons only (tooltips on hover), user avatar |

The sidebar is **always dark** — `--sidebar: var(--slate-900)` — regardless of system color scheme.
This creates a premium split-pane look.

### Logo Treatment

```
Expanded:  [OT]  OpenTroop
Collapsed: [OT]
```

The mark is a rounded square (`rounded-lg`) with `--sidebar-primary` (amber) background and
`--sidebar-primary-foreground` (dark) initials "OT". Phase 3: consider a custom SVG
(fleur-de-lis, flame, or tent silhouette).

### Navigation Items & Icons

All icons are from **Lucide React**. Selected for semantic clarity and visual distinctiveness:

| Tab | Lucide Icon | Rationale | Status |
|---|---|---|---|
| **Members** | `UserRound` | Individual person (vs. group shape) | Active |
| **Groups** | `Shield` | Patrols / organizational structure | Active |
| **Events** | `CalendarDays` | Calendar with date emphasis | Active |
| **Import** | `FolderInput` | File coming *in*, not generic upload arrow | Active |
| **Settings** | `Settings2` | Two-gear variant, more refined than single gear | Active |
| **Messaging** | `MessageSquare` | Communications hub | Grayed / future |
| **Advancement** | `Star` | Achievement / BSA advancement | Grayed / future |
| **Reports** | `BarChart3` | Data / reporting | Grayed / future |
| **Platform** | `Globe` | Global admin (platform-admin only) | Active |

Future nav items (Messaging, Advancement, Reports) are shown grayed-out (`opacity-40`,
`disabled`, with tooltip "Coming soon") to communicate the roadmap without making the sidebar
feel sparse.

### Active State

The shadcn sidebar uses `--sidebar-primary` for the active item indicator. Our amber token
(`--amber-400`) creates a warm, distinct highlight against the dark sidebar.

### Hover / Transition

- 150ms ease-out on sidebar width (collapse/expand) — shadcn default
- 80ms ease on item background (hover)
- Tooltip appears instantly in collapsed mode via shadcn `tooltip` prop

---

## 5. Page Layout

### Header Strip

```
[≡ trigger] │ [Page Title]                          [Actions]
```

- Height: `h-14` (56px)
- Title: `text-base font-semibold tracking-tight`
- Behavior: **sticky** (`sticky top-0 z-10`) with `backdrop-blur-sm` — floats over scrolling content
- Background: `bg-background/80` (translucent, shows content scrolling behind)
- Border: `border-b` (1px `--border`)
- Actions: right-aligned `ml-auto`, `Button size="sm"`

### Content Area

```
padding: p-4 md:p-6 (16–24px)
max-width: none — full-bleed tables
```

### Card / Table Surfaces

```css
border-radius: var(--radius-lg);    /* rounded-lg = 10px */
border: 1px solid var(--border);
box-shadow: shadow-sm;              /* subtle lift */
overflow: hidden;                    /* clips row hovers at corners */
```

---

## 6. Component Patterns

### Buttons

| Variant | Use |
|---|---|
| `default` (primary) | Primary CTA — "Add Member", "New Group", "Save" |
| `secondary` | Secondary actions — filters, toggles |
| `outline` | Tertiary — cancel, "View" in tables |
| `ghost` | Icon buttons, sidebar triggers |
| `destructive` | Delete, archive |

Sizing: `size="sm"` (h-8) in page headers; `size="default"` (h-9) in forms/sheets.

### Badges

Use the `TintBadge` pattern (inline span, not the shadcn `Badge` component) for semantic
status/type badges in tables — the rounded-full pill with tinted background reads better at small
sizes than the square `Badge` default.

```tsx
function TintBadge({ label, className }: { label: string; className: string }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${className}`}>
      {label}
    </span>
  )
}
```

### Tables

- **Card wrapper**: `rounded-lg border shadow-sm overflow-hidden`
- **Column headers**: `text-xs font-semibold uppercase tracking-wide text-muted-foreground`
- **Row hover**: `hover:bg-muted/40 transition-colors duration-75`
- **Clickable rows**: `cursor-pointer`
- **Selected row**: `bg-accent`
- **Null / empty values**: `<span className="text-muted-foreground">—</span>`

### Sheets (Detail Panels)

- Width: `w-[480px]` on desktop, full-width on mobile
- Header: icon + title + close button
- Body: sectioned with `<Separator />` between logical groups
- Footer: action buttons (`Save` / `Cancel`)

### Empty States

Consistent pattern across all data pages:

```tsx
<div className="flex flex-col items-center justify-center py-20 gap-4 text-center">
  <div className="rounded-full bg-muted p-4">
    <Icon className="h-7 w-7 text-muted-foreground" />
  </div>
  <div className="space-y-1">
    <p className="font-medium text-sm">No [things] yet.</p>
    <p className="text-xs text-muted-foreground">Helpful next-step suggestion.</p>
  </div>
  <Button size="sm">Add [Thing]</Button>  {/* only if applicable */}
</div>
```

### Loading States

Use the shadcn `Skeleton` component with shapes that mirror the expected content layout
(row-shaped skeletons for tables, not generic spinners). The `animate-pulse` class is applied
automatically by the `Skeleton` component.

---

## 7. Spacing & Radius

### Key Measurements

| Location | Value |
|---|---|
| Content padding (md+) | `p-6` (24px) |
| Card internal padding | `p-4` (16px) |
| Table cell padding | `px-4 py-3` |
| Table header cell padding | `px-4 py-2.5` |
| Gap between related items | `gap-2` (8px) |
| Gap between sections | `gap-6` (24px) |
| Form field spacing | `space-y-4` |

### Border Radius

```css
--radius: 0.625rem;  /* 10px base */
```

| Usage | Class | px |
|---|---|---|
| Inputs, buttons | `rounded-md` | 8px |
| Cards, tables, sheets | `rounded-lg` | 10px |
| Avatars, icon badges, pill badges | `rounded-full` | — |

---

## 8. Iconography

Always use **Lucide React** — never mix with other icon libraries.

| Context | Class | px |
|---|---|---|
| Inline with text | `h-4 w-4` | 16 |
| Sidebar nav | `h-4 w-4` | 16 |
| Table type indicator | `h-3.5 w-3.5` | 14 |
| Sheet / dialog header | `h-5 w-5` | 20 |
| Empty state (in muted circle) | `h-7 w-7` | 28 |
| Page header / button | `h-4 w-4` | 16 |

---

## 9. Motion & Animation

Keep animations subtle and purposeful — not decorative. Fast interactions feel premium.

| Element | Animation | Duration |
|---|---|---|
| Sidebar collapse/expand | width transition | 150ms ease-out |
| Sheet open/close | slide-in from right | 200ms ease-out (shadcn default) |
| Toast notifications | slide-up + fade | 180ms |
| Row hover background | color transition | 75ms |
| Button press | scale 0.98 | 80ms |
| Skeleton shimmer | gradient sweep | 1.5s loop |
| Page navigation | no full-page transition | — (keep snappy) |

`tw-animate-css` is already imported — use `animate-in`, `fade-in`, `slide-in-from-right`
utilities where appropriate.

---

## 10. Responsive Behavior

| Breakpoint | Sidebar | Content |
|---|---|---|
| `< md` (< 768px) | Hidden, sheet/drawer on demand | Full width |
| `md–lg` (768–1024px) | Collapsed (icon-only, 56px) | Fills remainder |
| `lg+` (> 1024px) | Expanded (220px) | Fills remainder |

The shadcn `SidebarProvider` manages collapse state. Use `isMobile` from `useSidebar()` hook
to conditionally render mobile-only UI.

---

## 11. Implementation Status

### Phase 1 — Foundation ✅
1. ✅ **Font** — Inter replaces Geist Sans in `layout.tsx`
2. ✅ **Color tokens** — `globals.css` updated with slate+amber palette, system dark mode
3. ✅ **Sidebar** — Dark sidebar, updated icons, amber active state, grayed future nav items
4. ✅ **Page header** — Sticky with backdrop-blur, `tracking-tight` title

### Phase 2 — Polish ✅
5. ✅ **Soft tinted badges** — Members (type/status) and Groups (type) pages
6. ✅ **Table headers** — Uppercase + `tracking-wide` column labels
7. ✅ **Empty states** — Icon-in-muted-circle pattern on Members and Groups pages
8. ✅ **Table cards** — `rounded-lg border shadow-sm overflow-hidden` wrappers

### Phase 3 — Delight (planned)
9. ☐ **Toast notifications** — Sonner integration
10. ☐ **Logo/brand mark** — Custom SVG icon for the "OT" sidebar badge
