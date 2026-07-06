# Navigation & Information Architecture Spec

**Status:** Draft
**Scope:** App-wide navigation shells and sidebar structure. The navigation model
(the sidebar is the single, complete map of the app — every feature findable there;
in-page tabs are allowed as within-page conveniences, never the only path; one
shared IA tree that mobile renders as bottom-tabs + stack + segmented controls) is
fixed by [ADR 0008](../adr/0008-navigation-sidebar-primary-ia.md) — this spec
details how that model is applied.

---

## Overview — three navigation shells

OpenTroop's UI splits into **three distinct navigation contexts**. They deliberately
do **not** share one navigation model, because they serve different audiences and have
different scale and branding needs.

| Shell | Audience | Chrome | Status |
|-------|----------|--------|--------|
| **Authenticated app** | Leaders, parents, scouts (tenant members) | Left **sidebar** | Exists (flat) |
| **Platform console** | Global/platform admins | Top **tab bar**, no sidebar | Exists (`/platform`) |
| **Public troop website** | Unauthenticated visitors + member "public view" | Troop-branded public header | Not built — CMS-driven |

The **public website is content management**, not a sidebar section. It is a separate
surface (troop branding, varies per tenant, mix of public and member-only content). Its
*editing* experience lives back in the app under **Settings → Website content**; its
*reading* experience is the public shell. Do not model the CMS as "just another
authenticated section."

The **platform console** keeps its existing top-tab pattern — it is a small, separate
admin surface and need not match the main app.

The rest of this spec is about the **authenticated app shell** (the sidebar), which is
where the bulk of upcoming features live.

---

## Decision rule: the sidebar is the complete map (ADR 0008)

The invariant is **findability** — the anti-TWH property. Apply consistently:

- **Every feature is reachable from the sidebar.** Nothing is findable *only* via a
  tab, a context menu, or a link buried in another page. The sidebar is the single,
  complete map of the app.
- **Every distinct page is a collapsible sidebar sub-item with its own route** —
  deep-linkable, with the active branch auto-expanding from the pathname. Same-data
  lenses that deserve findability (e.g. *Events* Calendar) get their own destination.
- **In-page tabs / segmented controls are allowed as a within-page convenience** —
  for same-data lenses (*Events* List/Calendar, *Advancement* by role) and a single
  record's sub-views (an event's Details vs. RSVP admin). They **supplement** the
  sidebar, never replace it. Prefer a **route-linked** switcher for lenses that are
  also sidebar destinations, so the URL and sidebar highlight stay in sync.
- **Mobile renders the same tree** with native chrome — bottom tab bar (top
  sections), stack navigation (drill-in), and a **segmented control** for same-data
  lenses. The IA is shared; the chrome is per-platform.

The **backbone is the collapsible sidebar**; tabs are a convenience layered on top,
never the sole way to reach a feature.

### Why collapsible sidebar (not top-tabs-per-section) as the backbone

- **Mobile-first:** horizontal tab bars break down past ~4 items on narrow screens
  (horizontal scroll is an anti-pattern). The sidebar collapses to a drawer where a
  vertical, expandable list reads cleanly.
- **Scale:** Money, Advancement, and Reports each want 4–8 subpages; tabs crowd, an
  expandable list does not.
- **Single source of truth:** one place to deep-link and to filter by permission; no
  ambiguity between a sidebar item and a separate tab strip.

---

## Authenticated app — sidebar structure

Top-level sections (each a sidebar item; sub-items are collapsible-group
destinations, each a real route, so every feature is findable here — ADR 0008):

| Section | Subpages (collapsible sidebar destinations) | Notes |
|---|---|---|
| **Home** | Announcements feed · upcoming events · my action items | New landing (today users drop on Members) |
| **Members** | Roster · **Bulk edit** (medical dates, etc.) · Relationships | Bulk editing = a destination |
| **Groups** | — | As-is |
| **Events** | Event List · Calendar · Event Types · Sign-ups · **Gallery** | List & Calendar are both findable destinations *and* share a route-linked in-page switcher; Gallery tied to events |
| **Advancement** | My advancement (scout) · My scouts (parent) · Troop (leader) · Awards | Role-varying lenses are permission-scoped destinations (may also expose a role segmented control) |
| **Messaging** | Announcements · Email/compose · Distribution lists · Sent history | |
| **Money** | Scout accounts · Transactions · Invoices · Budget | New domain |
| **Inventory** | Equipment · Assignments/check-out | New domain |
| **Resources** | Document & link library | |
| **Reports** | Report catalog *(params as in-page controls)* | Cross-cutting |
| **Settings / Admin** | Troop settings · **Roles & permissions** · Locations · **Website content (CMS)** | Event Types moved under **Events**; Import lives here too |

Two structural notes:

- A **Home / dashboard** landing replaces the current "redirect to Members" default.
- A **parent ("My Family") experience** is implemented as **permission-scoped views
  inside Members and Advancement**, not a separate top-level section — the same pages
  render a narrowed view for a parent vs. a leader.

---

## Rules of thumb

- **Depth cap: two levels.** Section → subpage. Never a third sidebar level. If a
  section needs more, its landing page becomes a **hub** (cards/links to the deeper
  pages).
- **Permission-driven visibility.** Sidebar items and sub-items render based on the
  member's effective permissions (`resolve_permissions`) — extend the existing
  `isPlatformAdmin` pattern in `app-sidebar.tsx`. An empty section is hidden, not shown
  disabled. This needs the session/permissions endpoint and `usePermissions()` hook —
  see [`session-permissions.md`](session-permissions.md).
- **Active state & deep-linking.** Sub-items are real routes (`/members/bulk`), not
  client-only state, so they are linkable and the active branch auto-expands from the
  pathname.
- **Collapsed sidebar (icon rail).** When the sidebar is icon-only, sections with
  children open their sub-list in a flyout (shadcn `SidebarMenuSub` supports this).

---

## Implementation notes

- The shadcn sidebar already provides everything needed: `SidebarGroup`,
  `SidebarGroupLabel`, `SidebarMenu`, `SidebarMenuSub`, `SidebarMenuSubButton`, and
  `Collapsible`. No new dependency.
- The sidebar is the complete map (ADR 0008): every feature is reachable from it,
  never *only* via a tab. In-page tabs / segmented controls are allowed as a
  within-page convenience (use the existing `Tabs` component or an inline segmented
  control); the mobile app renders same-data lenses as a segmented control.
- Keep `app-sidebar.tsx` as the single nav registry; model the nav as a typed array
  (`title`, `url`, `icon`, optional `children`, optional `requires: Permission`) so
  sections are declarative and testable.

---

## Open questions

- **Public website depth:** how much CMS flexibility per troop (fixed page types vs.
  freeform blocks)? Scoped in a later spec.
- **Parent onboarding:** how a claimed parent account discovers the "My Family" views.
- **Reports vs. per-section reporting:** whether reporting is one catalog or lives
  partly inside each domain section.
