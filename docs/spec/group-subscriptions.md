# Group Subscriptions Spec

**Status:** Draft
**Routes:** none (data model + API only in this phase; UI surface is the Group detail page and the Groups & Patrols section of Member edit)
**Pillar:** Roster & Relationships (Pillar 1) — prerequisite for Messaging (Pillar 2)

---

## Problem

Group membership is semantically "this person IS part of this group." But communications need a broader reach:

- A Scoutmaster may want all patrol communications even though they aren't a patrol member.
- A scout from Patrol Eagle may want to stay on Patrol Hawk's distribution list after transferring.
- Adult leaders want to receive PLC communications without being formal PLC members.

Creating shadow `_comms` groups would double group count, leak internal naming conventions, and create a maintenance burden. The solution is to separate **membership** (who IS in the group) from **subscription** (who WANTS group communications).

---

## Data Model

### New table: `GroupSubscription` (TrackedBase)

```
group_id       FK → groups.id         NOT NULL
member_id      FK → members.id        NOT NULL
notify_email   bool                   default TRUE
notify_sms     bool                   default FALSE

UniqueConstraint(tenant_id, group_id, member_id)  →  uq_group_subscriptions_group_member
```

`TrackedBase` supplies `id` (UUIDv7), `tenant_id`, `created_at`, `updated_at`, `is_deleted`.

**Why a separate table (not a flag on `GroupMember`):** Subscriptions and membership have different semantics. A subscriber doesn't appear on a roster, doesn't count toward headcount, and doesn't affect dynamic rule evaluation. Keeping them in a separate table means membership queries never need a `WHERE subscription_only = false` guard, and subscription preferences (channels, future: digest cadence) have a natural home.

### No changes to `Group` or `GroupMember`

Group membership semantics remain unchanged. `resolve_group_members()` continues to return only true members.

---

## Resolver: subscribers vs. members

Add `resolve_group_subscribers(group_id, session) → frozenset[member_id]` in `app/core/groups.py`:
- Returns member_ids from active (not soft-deleted) `GroupSubscription` rows for the group.
- Excludes members already in `resolve_group_members()` — no double-counting needed at the resolver level; the messaging layer handles the union.

For messaging, the combined audience is:

```
members(group) ∪ subscribers(group)
```

filtered by channel preferences and Member opt-out fields (see Messaging spec).

---

## API

All routes under `/groups/{group_id}/subscriptions`, gated by `event:read` to view and `member:write` to modify (subscription management is a leader task).

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/groups/{id}/subscriptions` | List current subscribers (member summaries + channel prefs) |
| `POST` | `/groups/{id}/subscriptions` | Add a subscriber `{member_id, notify_email, notify_sms}` |
| `PATCH` | `/groups/{id}/subscriptions/{member_id}` | Update channel prefs |
| `DELETE` | `/groups/{id}/subscriptions/{member_id}` | Remove subscriber (soft-delete) |

**`POST` body:**
```json
{ "member_id": "<uuid>", "notify_email": true, "notify_sms": false }
```

**409** if the member is already a subscriber (idempotent re-add should PATCH instead).
**400** if the member is already a full group member (no need to subscribe — they're in the member set).

---

## UI

### Member edit page — Groups & Patrols section

The existing `GroupMembershipEditor` shows group memberships as tag bubbles. Add a second row below for subscriptions, visually distinct (e.g., dashed border instead of solid, or a "bell" icon instead of a type icon):

```
Groups & Patrols
[🛡 Patrol Eagle ×]  [👥 PLC ×]          ← member of

Subscriptions
[🔔 Patrol Hawk ×]  [+ Subscribe to group…]  ← subscribed (not a member)
```

- Subscription bubbles show a bell icon and the group name. No type icon needed.
- The "Subscribe to group…" combobox lists groups the member is not already a member of AND not already subscribed to.
- Add/remove saves immediately (same pattern as group membership).
- Channel prefs (email/SMS toggles) are accessible via the bubble — clicking it opens a small inline popover with the two toggles.

### Group detail page (future)

When the Groups screen is built, its detail view should show two tabs or sections:
- **Members** — the resolved membership list (current behavior)
- **Subscribers** — the subscription list with channel toggles, add/remove controls

This is a placeholder; the Groups screen spec will own the full design.

---

## Constraints and edge cases

| Case | Behavior |
|------|----------|
| Member is already in group | `POST /subscriptions` returns 400 — they receive comms as a member |
| Subscriber added to group | Their `GroupSubscription` row should be soft-deleted (they no longer need a separate subscription) — enforce in the `POST /groups/{id}/members` handler |
| Group deleted (`is_deleted=true`) | Subscriptions are logically orphaned but retained for audit; messaging layer skips deleted groups |
| Member deactivated / soft-deleted | Messaging layer filters them out at send time via `Member.membership_status` and `Member.is_deleted` |
| Patrol swap (new patrol replaces old) | Subscriptions to the old patrol are NOT cleared — a scout who subscribed to Patrol Hawk's comms keeps that subscription even after transferring out |

---

## Open Questions

1. **Self-subscription:** Should members be able to manage their own subscriptions (e.g., from a "My Notifications" page), or is this always a leader-only action? Likely self-service once the member portal exists, but gated to `member:write` for now.

2. **Default subscriptions:** Should patrol leaders automatically be subscribed to sibling patrols? Probably not by default — let leaders opt in.

3. **Subscription visibility in member list:** Should the members list table show a "Subscriptions" column, or is this detail-only? Likely detail-only.
