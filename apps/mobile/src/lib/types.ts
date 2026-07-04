/** Thin aliases into the shared generated API types — never hand-write shapes. */

import type { components } from "@opentroop/api-types"

type Schemas = components["schemas"]

export type Membership = Schemas["MembershipRead"]
export type Member = Schemas["MemberRead"]
export type Event = Schemas["EventRead"]
export type EventType = Schemas["EventTypeRead"]
