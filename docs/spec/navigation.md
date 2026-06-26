# Navigation & Information Architecture Spec

**Status:** Draft
**Scope:** App-wide navigation shells, sidebar structure, and the rule for when to
use sidebar sub-navigation vs. in-page tabs.

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

## Decision rule: sidebar sub-items vs. tabs

Apply this consistently so new pages slot in predictably:

- **Collapsible sidebar sub-item = a destination.** Different data or a different CRUD
  area. Example: *Members → Bulk edit* is a different place than the roster.
- **In-page tab = a lens on the same subject.** Same underlying data, different
  view/filter. Example: *Events* List vs. Calendar (already shipped); *Advancement*
  viewed as a scout vs. parent vs. leader.

The **backbone is the collapsible sidebar**; tabs are a **within-page** control and are
never the primary section navigation.

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

Top-level sections (each a sidebar item; sub-items are collapsible groups, in-page
controls are *tabs*):

| Section | Subpages (collapsible) / in-page tabs | Notes |
|---|---|---|
| **Home** | Announcements feed · upcoming events · my action items | New landing (today users drop on Members) |
| **Members** | Roster · **Bulk edit** (medical dates, etc.) · Relationships | Bulk editing = a destination |
| **Groups** | — | As-is |
| **Events** | Calendar/List *(tabs)* · Sign-ups · **Gallery** | Photo gallery tied to events |
| **Advancement** | *Tabs by role:* My advancement (scout) · My scouts (parent) · Troop (leader) · Awards | Role-varying lenses → tabs |
| **Messaging** | Announcements · Email/compose · Distribution lists · Sent history | |
| **Money** | Scout accounts · Transactions · Invoices · Budget | New domain |
| **Inventory** | Equipment · Assignments/check-out | New domain |
| **Resources** | Document & link library | |
| **Reports** | Report catalog *(params as in-page controls)* | Cross-cutting |
| **Settings / Admin** | Troop settings · **Roles & permissions** · Event types · Locations · **Website content (CMS)** | Import lives here too |

Two structural notes:

- A **Home / dashboard** landing replaces the current "redirect to Members" default.
- A **parent ("My Family") experience** is implemented as **permission-scoped views
  inside Members and Advancement**, not a separate top-level section — the same pages
  render a narrowed view for a parent vs. a leader.

---

## Rules of thumb

- **Depth cap: two levels.** Section → subpage. Never a third sidebar level. If a
  section needs more, its landing page becomes a **hub** (cards or tabs to the deeper
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
- In-page tabs use the existing `Tabs` component (or the inline segmented control
  pattern already used on the Events page).
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
