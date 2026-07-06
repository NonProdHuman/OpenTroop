# 0008. Navigation IA: the sidebar is the complete map; tabs are within-page conveniences

- **Status:** Accepted
- **Date:** 2026-07-05

## Context

TroopWebHost — the product OpenTroop replaces — buried related features across
disjoint menu systems, so finding a given screen meant knowing which of several
unrelated menus hid it, and every task was slow to navigate. Avoiding that is a
primary product goal: there should be **one authoritative, always-complete map of
the app**, so every feature is findable in one predictable place.

`docs/spec/navigation.md` originally described a hybrid model (sidebar for
destinations, in-page tabs for "lenses on the same data"). The spirit was right,
but it never stated the actual invariant — *findability* — and it left ambiguous
whether a lens reached only through a tab counted as "findable." We considered the
opposite extreme (eliminate in-page tabs entirely, make every lens a sidebar
route) and rejected it: it throws away genuinely good in-context UX for
frequently-flipped lenses (Events List ↔ Calendar) for no findability gain.

We also want one navigation model that **carries from web to the Expo mobile app**,
sharing a single source of truth for the section/subpage tree.

## Decision

**The left sidebar is the single, complete map of the authenticated app: every
feature is reachable from it.** No feature is findable *only* through a tab, a
context menu, or a link buried inside another page. Concretely:

- The sidebar is an **accordion** — sections are collapsible groups, **at most one
  open at a time**. Every distinct page is a sidebar **destination with its own
  route** (deep-linkable; the active branch auto-expands from the pathname).
- **In-page tabs / segmented controls are permitted as a within-page
  convenience** — for same-data lenses (Events List/Calendar, Advancement role
  views) and for a single record's sub-views (an event's Details vs. RSVP admin).
  They **supplement** the sidebar; they never **replace** it. A tab is never the
  only way to reach something that deserves to be findable.
  - Applied first to **Events**: it becomes a sidebar folder with **Event List**
    (`/events`), **Calendar** (`/events/calendar`), and **Event Types**
    (`/events/types`) as findable destinations — *and* keeps a small in-page
    List/Calendar switcher that navigates between the two routes (route-linked, so
    URL and sidebar highlight stay in sync). Both findable *and* fast to flip.
- **Mobile renders the same tree** with native chrome — a **bottom tab bar** (top
  sections), **stack navigation** (drill-in), and a **segmented control**
  (same-data lenses). The segmented control is the native form of a lens; the IA
  is shared, the chrome is platform-specific.

## Consequences

- No buried features: one place to learn the whole app and to deep-link/permission-
  filter from. This is the anti-TWH property we are buying.
- In-context switching (List ↔ Calendar) stays available and fast via tabs/route-
  linked switchers, without forcing a sidebar round-trip.
- **Cost:** some intentional redundancy — a lens may be reachable both from the
  sidebar and from an in-page switcher. Accepted: findability and convenience are
  worth a duplicated affordance.
- Web and mobile must keep their navigation trees in sync; the tree is the
  contract, the chrome is per-platform.

## Alternatives considered

- **Tabs as primary section navigation (minimize the sidebar).** Rejected: this is
  the TWH failure mode — features scattered behind non-addressable local state,
  not findable from one map.
- **Eliminate in-page tabs entirely; every lens a sidebar route.** Considered and
  rejected: no findability gain over "lens is also a sidebar destination," and it
  discards good in-context UX (and resets filter/scroll state) for high-frequency
  flips.
- **Keep the loose hybrid as written.** Rejected: it never named the findability
  invariant, which is the actual requirement.
- **Copy the sidebar accordion literally onto mobile.** Rejected: a left-drawer
  accordion as *primary* phone nav fights platform conventions; bottom tabs +
  stack + segmented controls express the same IA natively.
