import { describe, expect, it } from "vitest"

import { EMPTY_MEMBER_FORM, toApiPayload, toFormState } from "./member-form"
import type { Member } from "@/types/api"

describe("toApiPayload", () => {
  // Regression: create trimmed first/last name but edit didn't, so the same
  // form input normalized differently depending on which page saved it.
  it("trims first and last name identically for create and edit", () => {
    const form = { ...EMPTY_MEMBER_FORM, first_name: "  Ann ", last_name: " Lee  " }
    const createPayload = toApiPayload(form)
    const editPayload = toApiPayload(form, true)
    expect(createPayload.first_name).toBe("Ann")
    expect(createPayload.last_name).toBe("Lee")
    expect(editPayload.first_name).toBe("Ann")
    expect(editPayload.last_name).toBe("Lee")
  })

  it("nullifies empty optional fields", () => {
    const payload = toApiPayload({ ...EMPTY_MEMBER_FORM, email: "  ", nickname: "" })
    expect(payload.email).toBeNull()
    expect(payload.nickname).toBeNull()
  })

  it("strips non-allowlisted fields when the caller lacks member:write", () => {
    const form = { ...EMPTY_MEMBER_FORM, first_name: "Ann", last_name: "Lee", phone: "555" }
    const payload = toApiPayload(form, false)
    expect(payload.phone).toBe("555")
    expect(payload).not.toHaveProperty("first_name")
    expect(payload).not.toHaveProperty("membership_status")
    expect(payload).not.toHaveProperty("oa_member")
  })
})

describe("toFormState", () => {
  it("round-trips a member through form state and back", () => {
    const member = {
      first_name: "Ann",
      last_name: "Lee",
      middle_name: null,
      name_suffix: null,
      nickname: "Annie",
      date_of_birth: "2010-04-01",
      member_type: "scout",
      membership_status: "active",
      bsa_id: "12345",
      email: null,
      phone: null,
      address_line1: null,
      address_line2: null,
      city: null,
      state: null,
      postal_code: null,
      country: "US",
      emergency_contact_1_name: null,
      emergency_contact_1_phone: null,
      emergency_contact_2_name: null,
      emergency_contact_2_phone: null,
      swim_classification: "swimmer",
      swim_date: null,
      medical_form_ab_date: null,
      medical_form_c_date: null,
      allergies: null,
      dietary_restrictions: null,
      notes: null,
      oa_member: false,
      oa_active: false,
      oa_election_date: null,
      oa_call_out_date: null,
      oa_ordeal_date: null,
      oa_brotherhood_date: null,
      oa_vigil_date: null,
      oa_vigil_name: null,
      oa_notes: null,
    } as Member

    const payload = toApiPayload(toFormState(member))
    expect(payload.first_name).toBe("Ann")
    expect(payload.nickname).toBe("Annie")
    expect(payload.middle_name).toBeNull()
    expect(payload.swim_classification).toBe("swimmer")
  })
})
