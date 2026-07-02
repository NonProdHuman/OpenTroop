"use client"

import { FormField, SectionTitle } from "@/components/form-helpers"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import type { Member, MemberStatus, MemberType, SwimClassification } from "@/types/api"

export type MemberFormState = {
  first_name: string
  middle_name: string
  last_name: string
  name_suffix: string
  nickname: string
  date_of_birth: string
  member_type: MemberType
  membership_status: MemberStatus
  bsa_id: string
  email: string
  phone: string
  address_line1: string
  address_line2: string
  city: string
  state: string
  postal_code: string
  country: string
  emergency_contact_1_name: string
  emergency_contact_1_phone: string
  emergency_contact_2_name: string
  emergency_contact_2_phone: string
  swim_classification: SwimClassification
  swim_date: string
  medical_form_ab_date: string
  medical_form_c_date: string
  allergies: string
  dietary_restrictions: string
  notes: string
  oa_member: boolean
  oa_active: boolean
  oa_election_date: string
  oa_call_out_date: string
  oa_ordeal_date: string
  oa_brotherhood_date: string
  oa_vigil_date: string
  oa_vigil_name: string
  oa_notes: string
}

export const EMPTY_MEMBER_FORM: MemberFormState = {
  first_name: "",
  middle_name: "",
  last_name: "",
  name_suffix: "",
  nickname: "",
  date_of_birth: "",
  member_type: "scout",
  membership_status: "active",
  bsa_id: "",
  email: "",
  phone: "",
  address_line1: "",
  address_line2: "",
  city: "",
  state: "",
  postal_code: "",
  country: "US",
  emergency_contact_1_name: "",
  emergency_contact_1_phone: "",
  emergency_contact_2_name: "",
  emergency_contact_2_phone: "",
  swim_classification: "nonswimmer",
  swim_date: "",
  medical_form_ab_date: "",
  medical_form_c_date: "",
  allergies: "",
  dietary_restrictions: "",
  notes: "",
  oa_member: false,
  oa_active: false,
  oa_election_date: "",
  oa_call_out_date: "",
  oa_ordeal_date: "",
  oa_brotherhood_date: "",
  oa_vigil_date: "",
  oa_vigil_name: "",
  oa_notes: "",
}

export function toFormState(m: Member): MemberFormState {
  return {
    first_name: m.first_name,
    middle_name: m.middle_name ?? "",
    last_name: m.last_name,
    name_suffix: m.name_suffix ?? "",
    nickname: m.nickname ?? "",
    date_of_birth: m.date_of_birth ?? "",
    member_type: m.member_type,
    membership_status: m.membership_status,
    bsa_id: m.bsa_id ?? "",
    email: m.email ?? "",
    phone: m.phone ?? "",
    address_line1: m.address_line1 ?? "",
    address_line2: m.address_line2 ?? "",
    city: m.city ?? "",
    state: m.state ?? "",
    postal_code: m.postal_code ?? "",
    country: m.country ?? "US",
    emergency_contact_1_name: m.emergency_contact_1_name ?? "",
    emergency_contact_1_phone: m.emergency_contact_1_phone ?? "",
    emergency_contact_2_name: m.emergency_contact_2_name ?? "",
    emergency_contact_2_phone: m.emergency_contact_2_phone ?? "",
    swim_classification: m.swim_classification,
    swim_date: m.swim_date ?? "",
    medical_form_ab_date: m.medical_form_ab_date ?? "",
    medical_form_c_date: m.medical_form_c_date ?? "",
    allergies: m.allergies ?? "",
    dietary_restrictions: m.dietary_restrictions ?? "",
    notes: m.notes ?? "",
    oa_member: m.oa_member,
    oa_active: m.oa_active,
    oa_election_date: m.oa_election_date ?? "",
    oa_call_out_date: m.oa_call_out_date ?? "",
    oa_ordeal_date: m.oa_ordeal_date ?? "",
    oa_brotherhood_date: m.oa_brotherhood_date ?? "",
    oa_vigil_date: m.oa_vigil_date ?? "",
    oa_vigil_name: m.oa_vigil_name ?? "",
    oa_notes: m.oa_notes ?? "",
  }
}

// Fields a member may edit on their own record without member:write.
const EDIT_ALLOWLIST = new Set([
  "phone", "email", "address_line1", "address_line2", "city", "state", "postal_code", "country",
  "emergency_contact_1_name", "emergency_contact_1_phone", "emergency_contact_2_name", "emergency_contact_2_phone",
  "medical_form_ab_date", "medical_form_c_date", "allergies", "dietary_restrictions",
])

// Convert empty strings to null for nullable fields before sending to the API.
export function toApiPayload(form: MemberFormState, canFullEdit = true): Partial<Member> {
  const nullify = (v: string) => v.trim() || null
  const payload: Partial<Member> = {
    first_name: form.first_name.trim(),
    middle_name: nullify(form.middle_name),
    last_name: form.last_name.trim(),
    name_suffix: nullify(form.name_suffix),
    nickname: nullify(form.nickname),
    date_of_birth: nullify(form.date_of_birth),
    member_type: form.member_type,
    membership_status: form.membership_status,
    bsa_id: nullify(form.bsa_id),
    email: nullify(form.email),
    phone: nullify(form.phone),
    address_line1: nullify(form.address_line1),
    address_line2: nullify(form.address_line2),
    city: nullify(form.city),
    state: nullify(form.state),
    postal_code: nullify(form.postal_code),
    country: nullify(form.country),
    emergency_contact_1_name: nullify(form.emergency_contact_1_name),
    emergency_contact_1_phone: nullify(form.emergency_contact_1_phone),
    emergency_contact_2_name: nullify(form.emergency_contact_2_name),
    emergency_contact_2_phone: nullify(form.emergency_contact_2_phone),
    swim_classification: form.swim_classification,
    swim_date: nullify(form.swim_date),
    medical_form_ab_date: nullify(form.medical_form_ab_date),
    medical_form_c_date: nullify(form.medical_form_c_date),
    allergies: nullify(form.allergies),
    dietary_restrictions: nullify(form.dietary_restrictions),
    notes: nullify(form.notes),
    oa_member: form.oa_member,
    oa_active: form.oa_active,
    oa_election_date: nullify(form.oa_election_date),
    oa_call_out_date: nullify(form.oa_call_out_date),
    oa_ordeal_date: nullify(form.oa_ordeal_date),
    oa_brotherhood_date: nullify(form.oa_brotherhood_date),
    oa_vigil_date: nullify(form.oa_vigil_date),
    oa_vigil_name: nullify(form.oa_vigil_name),
    oa_notes: nullify(form.oa_notes),
  }

  if (!canFullEdit) {
    for (const key of Object.keys(payload) as Array<keyof Member>) {
      if (!EDIT_ALLOWLIST.has(key)) {
        delete payload[key]
      }
    }
  }
  return payload
}

type SetField = <K extends keyof MemberFormState>(key: K, value: MemberFormState[K]) => void

// Identity → OA sections shared by the new and edit member pages. Fields outside
// EDIT_ALLOWLIST disable when canFullEdit is false; the caller renders its own
// Notes section (and, on edit, the family/group/position editors) after this.
export function MemberFormFields({
  form,
  set,
  canFullEdit = true,
  autoFocus = false,
}: {
  form: MemberFormState
  set: SetField
  canFullEdit?: boolean
  autoFocus?: boolean
}) {
  function handleText(key: keyof MemberFormState) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      set(key, e.target.value as MemberFormState[typeof key])
  }

  return (
    <>
      {/* ── Identity ─────────────────────────────────────── */}
      <SectionTitle>Identity</SectionTitle>
      <div className="grid grid-cols-2 gap-4">
        <FormField label="First name" required>
          <Input value={form.first_name} onChange={handleText("first_name")} autoFocus={autoFocus} disabled={!canFullEdit} />
        </FormField>
        <FormField label="Last name" required>
          <Input value={form.last_name} onChange={handleText("last_name")} disabled={!canFullEdit} />
        </FormField>
        <FormField label="Middle name">
          <Input value={form.middle_name} onChange={handleText("middle_name")} disabled={!canFullEdit} />
        </FormField>
        <FormField label="Suffix">
          <Input value={form.name_suffix} onChange={handleText("name_suffix")} placeholder="Jr., Sr., III…" disabled={!canFullEdit} />
        </FormField>
        <FormField label="Nickname / preferred name">
          <Input value={form.nickname} onChange={handleText("nickname")} disabled={!canFullEdit} />
        </FormField>
        <FormField label="Date of birth">
          <Input type="date" value={form.date_of_birth} onChange={handleText("date_of_birth")} disabled={!canFullEdit} />
        </FormField>
        <FormField label="Member type" required>
          <Select
            value={form.member_type}
            onValueChange={(v) => set("member_type", v as MemberType)}
            disabled={!canFullEdit}
          >
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="scout">Scout</SelectItem>
              <SelectItem value="adult">Adult</SelectItem>
            </SelectContent>
          </Select>
        </FormField>
        <FormField label="Status" required>
          <Select
            value={form.membership_status}
            onValueChange={(v) => set("membership_status", v as MemberStatus)}
            disabled={!canFullEdit}
          >
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="active">Active</SelectItem>
              <SelectItem value="inactive">Inactive</SelectItem>
              <SelectItem value="alumni">Alumni</SelectItem>
            </SelectContent>
          </Select>
        </FormField>
        <FormField label="BSA ID">
          <Input value={form.bsa_id} onChange={handleText("bsa_id")} disabled={!canFullEdit} />
        </FormField>
      </div>

      <Separator />

      {/* ── Contact ──────────────────────────────────────── */}
      <SectionTitle>Contact</SectionTitle>
      <div className="grid grid-cols-2 gap-4">
        <FormField label="Email">
          <Input type="email" value={form.email} onChange={handleText("email")} />
        </FormField>
        <FormField label="Phone">
          <Input type="tel" value={form.phone} onChange={handleText("phone")} />
        </FormField>
        <div className="col-span-2">
          <FormField label="Address line 1">
            <Input value={form.address_line1} onChange={handleText("address_line1")} />
          </FormField>
        </div>
        <div className="col-span-2">
          <FormField label="Address line 2">
            <Input value={form.address_line2} onChange={handleText("address_line2")} />
          </FormField>
        </div>
        <FormField label="City">
          <Input value={form.city} onChange={handleText("city")} />
        </FormField>
        <FormField label="State">
          <Input value={form.state} onChange={handleText("state")} maxLength={2} placeholder="CA" />
        </FormField>
        <FormField label="Postal code">
          <Input value={form.postal_code} onChange={handleText("postal_code")} />
        </FormField>
        <FormField label="Country">
          <Input value={form.country} onChange={handleText("country")} />
        </FormField>
      </div>

      <Separator />

      {/* ── Emergency Contacts ───────────────────────────── */}
      <SectionTitle>Emergency Contacts</SectionTitle>
      <div className="grid grid-cols-2 gap-4">
        <FormField label="Contact 1 name">
          <Input value={form.emergency_contact_1_name} onChange={handleText("emergency_contact_1_name")} />
        </FormField>
        <FormField label="Contact 1 phone">
          <Input type="tel" value={form.emergency_contact_1_phone} onChange={handleText("emergency_contact_1_phone")} />
        </FormField>
        <FormField label="Contact 2 name">
          <Input value={form.emergency_contact_2_name} onChange={handleText("emergency_contact_2_name")} />
        </FormField>
        <FormField label="Contact 2 phone">
          <Input type="tel" value={form.emergency_contact_2_phone} onChange={handleText("emergency_contact_2_phone")} />
        </FormField>
      </div>

      <Separator />

      {/* ── Medical ──────────────────────────────────────── */}
      <SectionTitle>Medical</SectionTitle>
      <div className="grid grid-cols-2 gap-4">
        <FormField label="Swim classification">
          <Select
            value={form.swim_classification}
            onValueChange={(v) => set("swim_classification", v as SwimClassification)}
            disabled={!canFullEdit}
          >
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="nonswimmer">Nonswimmer</SelectItem>
              <SelectItem value="beginner">Beginner</SelectItem>
              <SelectItem value="swimmer">Swimmer</SelectItem>
            </SelectContent>
          </Select>
        </FormField>
        <FormField label="Swim eval date">
          <Input type="date" value={form.swim_date} onChange={handleText("swim_date")} disabled={!canFullEdit} />
        </FormField>
        <FormField label="Health form A/B date">
          <Input type="date" value={form.medical_form_ab_date} onChange={handleText("medical_form_ab_date")} />
        </FormField>
        <FormField label="Health form C date">
          <Input type="date" value={form.medical_form_c_date} onChange={handleText("medical_form_c_date")} />
        </FormField>
        <div className="col-span-2">
          <FormField label="Allergies">
            <Textarea value={form.allergies} onChange={handleText("allergies")} rows={2} />
          </FormField>
        </div>
        <div className="col-span-2">
          <FormField label="Dietary restrictions">
            <Textarea value={form.dietary_restrictions} onChange={handleText("dietary_restrictions")} rows={2} />
          </FormField>
        </div>
      </div>

      <Separator />

      {/* ── Order of the Arrow ───────────────────────────── */}
      <div className="flex items-center gap-3">
        <SectionTitle>Order of the Arrow</SectionTitle>
        <label className="flex items-center gap-2 text-sm cursor-pointer ml-auto">
          <input
            type="checkbox"
            checked={form.oa_member}
            onChange={(e) => set("oa_member", e.target.checked)}
            className="rounded"
            disabled={!canFullEdit}
          />
          OA member
        </label>
      </div>
      {form.oa_member && (
        <div className="grid grid-cols-2 gap-4">
          <label className="flex items-center gap-2 text-sm col-span-2 cursor-pointer">
            <input
              type="checkbox"
              checked={form.oa_active}
              onChange={(e) => set("oa_active", e.target.checked)}
              className="rounded"
              disabled={!canFullEdit}
            />
            Active OA member
          </label>
          <FormField label="Election date">
            <Input type="date" value={form.oa_election_date} onChange={handleText("oa_election_date")} disabled={!canFullEdit} />
          </FormField>
          <FormField label="Call-out date">
            <Input type="date" value={form.oa_call_out_date} onChange={handleText("oa_call_out_date")} disabled={!canFullEdit} />
          </FormField>
          <FormField label="Ordeal date">
            <Input type="date" value={form.oa_ordeal_date} onChange={handleText("oa_ordeal_date")} disabled={!canFullEdit} />
          </FormField>
          <FormField label="Brotherhood date">
            <Input type="date" value={form.oa_brotherhood_date} onChange={handleText("oa_brotherhood_date")} disabled={!canFullEdit} />
          </FormField>
          <FormField label="Vigil date">
            <Input type="date" value={form.oa_vigil_date} onChange={handleText("oa_vigil_date")} disabled={!canFullEdit} />
          </FormField>
          <FormField label="Vigil name">
            <Input value={form.oa_vigil_name} onChange={handleText("oa_vigil_name")} disabled={!canFullEdit} />
          </FormField>
          <div className="col-span-2">
            <FormField label="OA notes">
              <Textarea value={form.oa_notes} onChange={handleText("oa_notes")} rows={2} disabled={!canFullEdit} />
            </FormField>
          </div>
        </div>
      )}
    </>
  )
}
