# US Legal & Policy Landscape for OpenTroop

Status: analysis / reference (July 2026). **This is engineering research, not legal
advice** — before SaaS launch, have a lawyer review the privacy policy, terms of
service, and the parental-consent flow. This document exists to inform feature
design (see #122, #121, #85, #146, #145) and the disclosure text shown at account
creation.

OpenTroop's exposure is unusual for its size: it is an online service whose core
data set is **rosters of minors**, including health information (allergies,
medical-form dates, and eventually full AHMR data per #85). That combination —
children's data + health data — is treated as maximally sensitive by essentially
every regime below.

---

## 1. Who is responsible: SaaS vs self-hosted

The same code ships in two postures with very different legal footprints:

| | SaaS (opentroop.app) | Self-hosted (one troop) |
|---|---|---|
| Legal "operator" / data controller | **The platform** (us), with tenants as co-controllers of their data | The troop / chartered organization |
| COPPA operator status | Yes, if for-profit (see §2.1) | Usually no — FTC Act generally doesn't reach nonprofits; most troop charter orgs are nonprofits |
| State privacy laws | Apply per thresholds; some cover nonprofits | Mostly exempt (nonprofit + below thresholds), **except** breach-notification and some security laws, which apply to everyone |
| State breach notification | Us (and contractually, notify tenants) | The troop |
| Scouting America policy | Applies to how troops *use* the product; we must make compliant use easy and non-compliant use hard | Same |

Design consequence: **build to the SaaS (strictest) standard and let self-host
inherit it.** Never rely on a nonprofit exemption in feature design — exemptions
protect the self-hosted troop, not the platform, and several state laws now cover
nonprofits anyway (Colorado, Oregon, Delaware, New Jersey).

---

## 2. Federal law

### 2.1 COPPA — Children's Online Privacy Protection Act (the big one)

Applies to operators of commercial online services **directed to children under
13**, or any operator with **actual knowledge** it collects personal information
from a child under 13. A scouting platform whose users include Cub-age and young
Scouts BSA members is realistically child-directed in part, and we will always
have actual knowledge (date_of_birth is on the roster). Assume COPPA applies to
the SaaS in full.

The FTC's amended COPPA Rule was finalized April 2025 and is **fully effective as
of April 22, 2026** — i.e., the amended rule, not the 2013 rule, is our baseline:

- **Verifiable parental consent (VPC)** before collecting personal info *from* a
  child, with **separate opt-in consent** required for any disclosure to third
  parties (e.g., ad tech — which we simply should never do). Newly approved VPC
  methods include **text-message-based consent** and knowledge-based
  authentication, alongside the classics (credit-card transaction, signed form,
  ID match).
- **Expanded "personal information"**: now includes biometrics, government IDs,
  phone numbers, audio recordings, and precise-ish geolocation.
- **Written, public data-retention policy** — children's data may be kept only
  as long as necessary for the purpose collected, then deleted. **Indefinite
  retention is explicitly prohibited.** This directly constrains our
  soft-delete-tombstones-forever model → hard-delete pipeline in #121 is a
  compliance requirement, not a nice-to-have.
- **Written children's data security program** with safeguards proportional to
  sensitivity — maps to #116/#117/#122.
- **Direct notice to parents** describing what is collected and why, plus a
  COPPA-specific section in the privacy policy.
- **Data-minimization tie-in**: an operator may not condition a child's
  participation on collecting more personal info than reasonably necessary.

Two distinctions that matter enormously for our design:

1. **Collection *from* a child vs. data *about* a child.** COPPA regulates online
   collection *from* the child (accounts, messages the child types, photos the
   child uploads, identifiers from the child's device). A leader or parent typing
   a scout's allergy list into the roster is an adult providing data about a
   child — not COPPA "collection," though state laws still treat it as
   children's/health data. This means **the roster can fully exist without any
   COPPA consent machinery; the machinery is triggered when the scout gets a
   login.**
2. **"Collection" includes letting a child make PII publicly available** — chat,
   comments, profile fields, photo uploads. Feature-gating these for under-13
   accounts removes most of the ongoing COPPA surface (see §6).

**Nonprofit nuance:** COPPA rides on FTC Act jurisdiction, which generally
excludes true nonprofits. A self-hosted troop instance is very likely outside
COPPA. The hosted SaaS is inside it if operated commercially (subscriptions —
see billing in #121). If OpenTroop-the-org were itself a nonprofit, the exemption
*might* apply, but the FTC construes it narrowly (nonprofits operating for
members' profit are covered) — do not architect around this.

### 2.2 Pending federal legislation — watch list

- **KOSA / KIDS Act**: the House passed the Kids Internet and Digital Safety
  package in June 2026; Senate fate uncertain (duty-of-care provision stripped,
  Senate sponsors object). Aimed at large platforms, but definitions matter —
  track it.
- **COPPA 2.0** (Children and Teens' Online Privacy Protection Act): a version
  passed the Senate; would extend protections to teens 13–16 (consent from the
  teen, ad-targeting bans, eraser button). If enacted, our "13+ scouts are
  simpler" assumption weakens — another reason to build one consent framework
  covering all minors rather than an under-13 special case.

### 2.3 CAN-SPAM Act (email)

Commercial-ish bulk email must honor opt-outs promptly, identify the sender with
a physical postal address, and not use deceptive subjects. `Member.email_opt_out`
/ `email_bounced` already exist; the send queue (#78) skipping them is the
enforcement point, and bounce webhooks (#80) close the loop. Troop operational
mail (event reminders) is largely "transactional/relationship" content, which is
lighter-touch — but building opt-out handling universally is cheaper than
classifying messages.

### 2.4 TCPA (SMS) — higher risk than email

Text messaging (#77) requires **prior express consent** for informational texts
(and written consent if anything promotional), per-recipient opt-out honoring
(`STOP`), and sane sending hours. Statutory damages are $500–$1,500 *per text*,
and TCPA class actions are a cottage industry. Additionally, US carriers require
**10DLC campaign registration** (via Twilio/Telnyx) with declared use-case and
opt-in evidence before application-to-person SMS will deliver at volume.
`sms_opt_in` already exists on `Member` — it must remain strictly opt-in (never
default-on, never inferred), with the consent timestamp/source recorded.

### 2.5 Laws that mostly *don't* apply (say so to avoid cargo-culting)

- **HIPAA** — applies to covered entities (providers, insurers) and their
  business associates. A troop storing a scout's AHMR is neither. HIPAA does
  **not** apply, but users will *expect* HIPAA-grade handling of medical data,
  and state health-privacy laws (e.g., Washington's My Health My Data, which has
  a private right of action and covers nonprofits) can reach consumer health
  data. Treat medical fields as if regulated: gate behind `member:read_medical`,
  audit reads (#122), encrypt, minimize.
- **FERPA** — education records held by schools receiving federal funds; not us,
  even for school-chartered units (the troop isn't the school acting as such).
- **CIPA** — schools/libraries with E-Rate funding; not us.

---

## 3. State law

### 3.1 Comprehensive consumer privacy laws (~20 states and growing)

California (CCPA/CPRA), Virginia, Colorado, Connecticut, Utah, Texas, Oregon,
Montana, Delaware, New Jersey, and more. Common structure, varying thresholds
(e.g., 100k residents' data processed, or 25k + revenue share from selling
data). Early-stage OpenTroop will be under most thresholds, but:

- **Children's data and health data are "sensitive data"** in nearly all of
  them, requiring opt-in consent to process — thresholds don't change the
  reputational bar, and Texas's law applies regardless of processing volume to
  any non-small-business.
- **Several cover nonprofits** (Colorado, Oregon, Delaware, New Jersey) — the
  self-hosted exemption story is thinner than it used to be.
- **CCPA minors' rule**: opt-in consent required to "sell/share" data of
  consumers under 16 (parent consents under 13). We should simply never
  sell/share — state that in the privacy policy.
- Rights to access, correct, delete, and portability → the tenant data export
  and hard-delete work in #121 is also the substrate for individual
  rights-requests.

### 3.2 Children-specific state laws

A fast-moving patchwork: age-appropriate design codes (Maryland's is in effect;
California's is enjoined), social-media parental-consent laws (Utah, Texas HB
18, Louisiana, Florida — several partially enjoined on First Amendment grounds),
and app-store age-verification laws (Texas, Utah, Louisiana, Alabama — the
Alabama law effective Jan 2027 matters for the future mobile app, #93, since
app stores will surface parental-consent status to developers). These mostly
target social-media-shaped services. OpenTroop is not one — but **the more we
add open-ended messaging, photo feeds, and profiles, the more we drift toward
their definitions.** The Scouting America guardrails in §4 (no private channels,
no youth DMs) conveniently keep us out of the blast radius; treat that as a
design constraint, not just BSA policy.

### 3.3 Laws that apply to everyone, at any size, including self-hosters

- **Breach notification** — all 50 states. Any entity holding residents'
  personal information (name + SSN/driver's-license/medical/account data) must
  notify affected individuals (and often the AG) after a breach. Needs: an
  incident-response runbook, and contractual clarity that in SaaS mode we detect
  and notify tenants, who notify their families.
- **Data-security statutes** — e.g., New York SHIELD Act requires "reasonable
  safeguards" from *any* entity (nonprofits included, everywhere in the US)
  holding NY residents' private info. Massachusetts 201 CMR 17 requires a
  written information security program (WISP). The #122 security program
  satisfies these in one shot.
- **Minors' likeness/publicity rights** — photo galleries (#145) need per-member
  media-consent flags with parent-granted consent for minors; several states
  require parental consent for commercial use of a minor's image, and
  BSA practice uses talent-release forms for exactly this reason.

---

## 4. Scouting America (BSA) policy

Not law, but binding on every unit using the product, and *the* differentiator
if we enforce it structurally where TroopWebHost merely assumes it. Sources: the
Barriers to Abuse, the Guide to Safe Scouting, Digital Privacy / Social Media
Guidelines, and the 2026 Safeguarding Youth training rollout.

1. **No one-on-one adult↔youth contact — including digitally.** Any electronic
   communication between an adult and a youth member (text, email, DM, video
   call) must openly include another authorized adult (registered leader or the
   scout's parent/guardian). **Feature implication for #146: the messaging layer
   must make 1:1 adult→minor messages structurally impossible** — every thread
   involving a minor must have ≥2 adults (auto-CC a parent via
   `MemberRelationship`, or a second leader), visibly, not BCC. This should be
   an invariant in the send path, not a UI convention.
2. **No private channels.** Unit social media must be public or
   parent-accessible; invite-only youth spaces are prohibited. Implication:
   no youth-only group chats; parents of resolved group members can always see
   group communications (the existing `include_parents` /
   `cc_parents_on_messages` machinery is the right shape).
3. **Two-deep leadership** on all activities, including virtual meetings.
   Implication: the #122 two-deep event check should extend to events flagged
   `is_online`.
4. **Youth Protection Training / Safeguarding Youth** — all adults must complete
   the new Safeguarding Youth training (deadline May 31, 2026) with **annual**
   refreshers now required. Implication for #122's YPT tracking: model it as a
   recurring annual expiration, not a multi-year one.
5. **AHMR confidentiality** — health records are to be shared only with those
   who need them (unit leader, medical staff), and returned/destroyed after the
   activity. Implication for #85: per-event access windows and post-event
   destruction/archival policy, not permanent open access.
6. **Media consent** — units use talent-release/photo-consent practice;
   the #145 gallery must model per-member consent granted by a parent.

---

## 5. What this means at account creation (disclosures & consent)

Artifacts we need before SaaS launch:

- **Privacy policy** with a COPPA direct-notice section (what we collect from
  children, why, retention, parental rights to review/delete/refuse), a
  no-sale/no-third-party-disclosure statement, and the **written retention
  policy** the amended COPPA Rule requires to be public.
- **Terms of service** allocating SaaS-vs-tenant responsibilities (who notifies
  in a breach, tenant's duty to obtain any consents for data they enter about
  families, acceptable use = Scouting America guidelines).
- **Parental-consent record** (new model): who consented, for which child, when,
  via which method, covering which scopes (account creation; media/photos; SMS).
  Auditable and revocable. This is also where photo consent (#145) and SMS
  opt-in (#77) live — one consent ledger, multiple scopes.
- **Signup disclosures**: age-tier determination (from roster DOB, not a
  self-asserted age gate), a short-form notice at claim time, links to policy.
- **SMS opt-in language** meeting TCPA/10DLC requirements (what, how often,
  "msg&data rates," STOP/HELP).

---

## 6. Recommendation: under-13 accounts — allow, parent-mediated, feature-gated

Banning under-13 accounts would gut the product (a huge share of Scouts BSA and
all Cub Scouts are under 13). COPPA does not require a ban — it requires
verifiable parental consent and minimization. Recommended model:

**Three account tiers, driven by roster `date_of_birth` + `member_type`:**

| Tier | Consent | Capabilities |
|---|---|---|
| Adult | Standard ToS | Full (per RBAC) |
| Youth 13–17 | Parent-initiated invite (recommended even though COPPA doesn't require it; Scouting America practice does, and COPPA 2.0 may) | RSVP, own calendar/iCal, view own advancement, group-visible content; messaging only within YP guardrails |
| Youth <13 | **Verifiable parental consent, recorded** | Read-mostly: view events/calendar, own RSVP (or parent-approved RSVP), own advancement status. **Disabled: free-form messaging, photo upload, profile editing beyond nickname, any content creation visible beyond the troop** |

**Consent flow = the existing invite/claim machinery, extended.** The scout's
parent (identified via `MemberRelationship` `parent_of`/`guardian_of`, holding a
claimed, verified account) triggers the child's invite, sees the COPPA direct
notice, and consents — a parent-initiated, authenticated action that fits the
amended rule's VPC framework (text-message consent is now an approved method,
which matches this flow well; document the method and keep the record). An admin
inviting a scout under 13 without a linked consenting parent should be blocked,
not warned.

**Why feature-gating works legally:** COPPA's ongoing obligations attach to what
we *collect from* the child. A read-mostly under-13 account collects login
credentials and RSVP taps — near-minimal. No chat, no uploads means the child
never makes PII publicly available through us. The rich data (medical, contacts)
is entered *about* the child by adults, outside COPPA's collection definition,
and protected instead by the #122 gating/audit layer. This keeps the compliance
surface small while preserving the product's value to young scouts.

**Additional recommendations, in priority order:**

1. Treat #121's hard-delete/retention pipeline as **COPPA-mandated** (retention
   limits are enforceable as of April 2026) — raise its priority accordingly.
2. Make the #146 messaging spec encode the YP invariants (no 1:1 adult↔minor,
   auto-include parent/second adult, no youth-only threads) as send-path
   invariants with tests.
3. Add the consent-ledger model (one table, scoped consents: account, media,
   SMS) as part of the under-13 account work — it's the substrate for #77, #145,
   and this document's signup flow.
4. Never add ad tech, third-party analytics with PII, or data sale — it
   triggers the harshest provisions of every regime above and is off-brand.
5. For self-host, ship the same defaults and include a short "operator
   responsibilities" section in the deployment docs (breach notification,
   retention, their state's laws).
6. Revisit this document when the KOSA/KIDS package or COPPA 2.0 is enacted,
   and before the mobile app ships (app-store age-verification laws start
   biting Jan 2027).

---

## Sources

- [FTC COPPA amendments — Finnegan: amended rule in full effect](https://www.finnegan.com/en/insights/articles/coppas-amended-rule-is-now-in-full-effect-what-operators-need-to-know.html)
- [COPPA amendment compliance deadline — Hunton](https://www.hunton.com/privacy-and-cybersecurity-law-blog/coppa-rule-amendment-compliance-deadline-approaches)
- [COPPA retention requirements — Fenwick](https://www.fenwick.com/insights/publications/what-the-amended-coppa-rule-means-for-data-retention-practices)
- [FTC COPPA enforcement priorities — Davis Polk](https://www.davispolk.com/insights/client-update/ftc-prioritizes-coppa-enforcement-new-compliance-obligations-take-effect)
- [State children's privacy laws 2026 — Holland & Knight](https://www.hklaw.com/en/insights/publications/2026/04/states-push-childrens-privacy-laws-forward)
- [State app store / design code laws — Loeb & Loeb](https://www.loeb.com/en/insights/publications/2026/06/childrens-online-privacy-2026-state-app-store-design-code-and-social-media-laws)
- [Children's privacy legislation tracker — Mayer Brown](https://www.mayerbrown.com/en/insights/publications/2026/01/little-users-big-rules-tracking-childrens-privacy-legislation)
- [KIDS Act House passage — TechPolicy.Press](https://www.techpolicy.press/bipartisan-smorgasbord-of-childrens-online-safety-legislation-passes-the-house/)
- [Scouting America Youth Protection](https://www.scouting.org/training/youth-protection/)
- [Youth Protection and Adult Leadership (Barriers to Abuse)](https://www.scouting.org/health-and-safety/gss/gss01/)
- [Digital Safety and Online Scouting Activities](https://www.scouting.org/health-and-safety/safety-moments/digital-safety-and-online-scouting-activities/)
- [Scouting America Social Media Guidelines](https://scoutingwire.org/social-media-guidelines/)
