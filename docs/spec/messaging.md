# Messaging Spec

**Status:** Draft
**Routes:** `/messages` (compose + history)
**Pillar:** Communication (Pillar 2) — depends on Group Subscriptions spec

---

## Overview

Leaders need to send email and SMS to troop members and their families. The key design
decisions in this spec are:

1. **Audience is resolved at send time** — no persistent shadow groups for "members + parents."
   The resolver walks `MemberRelationship` at composition time.
2. **Groups are the primary targeting unit**, with per-message audience expansion options.
3. **Channel selection respects Member opt-out fields** (`email_opt_out`, `email_bounced`,
   `sms_opt_in`).
4. **Delivery infrastructure** (email service, SMS gateway) is out of scope for this spec.
   This spec covers the data model, audience resolution, and UI.

---

## Actors and Permissions

| Permission | Capability |
|-----------|------------|
| `event:read` (any member) | View message history for groups they belong to |
| `member:write` | Compose and send messages |
| Future: `messaging:send` | Reserved — use `member:write` until messaging grows into its own permission domain |

---

## Audience Model

A message targets one or more **groups** (including patrol groups). For each group, the
composer selects an **audience expansion**:

| Expansion | Who receives the message |
|-----------|--------------------------|
| **Members** | `resolve_group_members(group_id)` ∪ `resolve_group_subscribers(group_id)` |
| **Members + Parents/Guardians** | Above + their `parent_of` / `guardian_of` relatives |
| **Parents/Guardians only** | Parents/guardians of members (not the members themselves) — useful for younger scout patrols |

The default is **Members** (includes subscribers). The expansion choice is per-message,
not stored on the group.

**Why not persistent shadow groups for parents:** `MemberRelationship` is the authoritative
source. A shadow group would need to be re-synced whenever a relationship is added, changed,
or removed. Resolving at send time is always accurate and adds no maintenance burden.

### Parent/guardian resolution

```
parent_member_ids(group_id, session):
  member_ids = resolve_group_members(group_id) ∪ resolve_group_subscribers(group_id)
  return {
    rel.from_member_id
    for rel in MemberRelationship
    where rel.to_member_id in member_ids
    and rel.relationship_type in ("parent_of", "guardian_of")
    and not rel.is_deleted
  }
```

The resolver is in `app/core/messaging.py` (new file). It is the only place parent expansion
logic lives — not duplicated across email/SMS handlers.

---

## Channels

Each message is sent on one or both channels:

| Channel | Gating field on `Member` |
|---------|--------------------------|
| Email | `email_opt_out = false` AND `email_bounced = false` AND `email IS NOT NULL` |
| SMS | `sms_opt_in = true` AND `phone IS NOT NULL` |

Subscribers also have per-channel prefs on `GroupSubscription` (`notify_email`, `notify_sms`).
A subscriber only receives on a channel if **both** their `GroupSubscription` preference and
their `Member` opt-out state allow it.

For parent/guardian expansion, parents are contacted on the channels gated by their own
`Member` record (their `email_opt_out`, `sms_opt_in`, etc.) — not the scout's preferences.

---

## Data Model

### `Message` (TrackedBase)

```
subject          str          NOT NULL
body             text         NOT NULL
channel          MessageChannel  enum: email | sms | both
audience_type    AudienceType    enum: members | members_and_parents | parents_only
status           MessageStatus   enum: draft | scheduled | sending | sent | failed
scheduled_at     datetime?    NULL = send immediately on POST /messages/{id}/send
sent_at          datetime?    set when delivery is complete
sent_by_id       FK → members.id
```

### `MessageGroup` (TrackedBase)

Links a message to one or more groups. The expansion is stored per row so a single message
can target "Patrol Eagle (members only)" and "PLC (members + parents)" simultaneously.

```
message_id       FK → messages.id
group_id         FK → groups.id
audience_type    AudienceType    overrides the message-level default if set

UniqueConstraint(tenant_id, message_id, group_id)
```

### `MessageRecipient` (TrackedBase)

Snapshot of the resolved recipient list at send time. This is the audit trail; it lets
leaders see exactly who received a message even if group membership changes later.

```
message_id       FK → messages.id
member_id        FK → members.id
channel          MessageChannel  enum: email | sms
delivered        bool            default False
delivered_at     datetime?
error            str?            delivery error message if failed
```

`MessageRecipient` rows are written when the message transitions from `draft → sending`.
They are **not** written for drafts or scheduled messages until send time.

---

## API

### Compose

```
POST /messages/
```

Body:
```json
{
  "subject": "Campout reminder",
  "body": "Don't forget sleeping bags!",
  "channel": "email",
  "group_targets": [
    { "group_id": "<uuid>", "audience_type": "members_and_parents" },
    { "group_id": "<uuid>", "audience_type": "members" }
  ],
  "scheduled_at": null
}
```

Returns the created `Message` in `draft` status plus a resolved `preview` of recipient
counts (not full member list — just counts by channel):

```json
{
  "message": { ... },
  "preview": {
    "email_recipients": 34,
    "sms_recipients": 12,
    "deduplicated_total": 38
  }
}
```

Deduplication: a member targeted by multiple groups (e.g., appears in both Patrol Eagle and
PLC) receives the message only once per channel.

### Send

```
POST /messages/{id}/send
```

Transitions `draft → sending`, resolves and writes `MessageRecipient` rows, enqueues
delivery. Returns 409 if message is already sent or sending.

### Preview (recipient list)

```
GET /messages/{id}/recipients/preview
```

Returns the resolved recipient list **before** send — full member summaries. Used by the
compose UI to let leaders verify the audience before committing.

### History

```
GET /messages/               list (paginated, filter by group/status/date)
GET /messages/{id}           detail + delivery stats
GET /messages/{id}/recipients  full recipient list with delivery status
```

---

## UI

### Compose view (`/messages/new`)

A single-page compose form:

```
Subject: [___________________________________]

Message:
[_____________________________________________]
[_____________________________________________]

Channel:  [✉ Email]  [📱 SMS]  [Both]

Target groups:
  [+ Add group]
  ┌─────────────────────────────────────────┐
  │ 🛡 Patrol Eagle    Audience: [Members ▾] │
  │ 👥 PLC             Audience: [Members + Parents ▾] │
  └─────────────────────────────────────────┘

Preview:
  📧 34 email recipients  📱 12 SMS recipients
  [View full list]

[Save draft]  [Schedule…]  [Send now →]
```

The **Audience** dropdown per group shows:
- Members (default)
- Members + Parents/Guardians
- Parents/Guardians only

**Preview count** updates live as groups and audience types are changed (debounced call to
`GET /messages/{id}/recipients/preview` or a dedicated preview endpoint).

**View full list** opens a sheet showing the resolved member list with name, channel(s) they'll
receive on, and any opt-out indicators.

### Message history (`/messages`)

A simple table: date sent · subject · groups targeted · recipient count · status.
Clicking a row opens the message detail with delivery stats.

---

## Constraints and edge cases

| Case | Behavior |
|------|----------|
| Member appears in multiple target groups | Deduplicated — receives once per channel |
| Member has `email_opt_out = true` | Excluded from email channel silently (counted in preview as "opted out") |
| Member has `email_bounced = true` | Excluded from email; surface in preview as "bounced" |
| Member has `sms_opt_in = false` | Excluded from SMS |
| Parent is also a troop member | They appear once — parent expansion doesn't add duplicates if already in member set |
| Parent has no email or phone | Excluded from that channel; no error |
| Group has no members | `MessageGroup` is valid; results in zero recipients for that group |
| Message sent to deleted group | Blocked at compose time; group picker excludes `is_deleted=true` groups |

---

## Open Questions

1. **Delivery infrastructure:** Which email provider (SendGrid, SES, Postmark) and SMS gateway
   (Twilio, Vonage)? This is a deployment/ops decision. The `MessageRecipient` table is
   delivery-provider-agnostic; the provider is wired in behind a `send_email()` /
   `send_sms()` abstraction in `app/core/messaging.py`.

2. **Reply handling:** If a recipient replies to a group email, where does it go? Options:
   a) a troop reply-to address that forwards to the sender,
   b) the sender's personal email,
   c) discard. Punted — decide when delivery infrastructure is chosen.

3. **Attachments:** Leaders will want to attach permission slips, maps, etc. Treat as
   follow-on; the `Message` body is plain text/HTML for now.

4. **Two-way SMS:** BSA compliance requires an opt-out keyword (STOP). The SMS gateway
   handles this, but we need to sync `sms_opt_in = false` back to the `Member` record when
   a STOP is received. Requires a webhook from the gateway.

5. **Permission slip distribution via messaging:** Events with `require_permission_slip=true`
   may want a "send permission slip" action that pre-fills the message body and targets event
   participants. Treat as an event-specific messaging flow, built on top of this foundation.

6. **Rate limiting and abuse:** A platform-level concern — limit messages per tenant per day
   to prevent misuse on the SaaS platform.
