"use client"

import { useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { useMember, useMembers, useUpdateMember } from "@/hooks/use-members"
import { useGroups, useMemberGroups } from "@/hooks/use-groups"
import { useMemberPositions } from "@/hooks/use-member-positions"
import { usePositions } from "@/hooks/use-positions"
import { usePermissions } from "@/hooks/use-session"
import { FamilyRelationshipsEditor } from "@/components/family-relationships-editor"
import { GroupMembershipEditor } from "@/components/group-membership-editor"
import { MemberPositionsEditor } from "@/components/member-positions-editor"
import { PageHeader } from "@/components/page-header"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import { useRelationships } from "@/hooks/use-relationships"
import type { Member, MemberStatus, MemberType, SwimClassification } from "@/types/api"

type FormState = {
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

function toFormState(m: Member): FormState {
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

// Convert empty strings back to null for nullable fields before sending to API
function toApiPayload(form: FormState): Partial<Member> {
  const nullify = (v: string) => v.trim() || null
  return {
    first_name: form.first_name,
    middle_name: nullify(form.middle_name),
    last_name: form.last_name,
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
}

function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground pt-2">
      {children}
    </h2>
  )
}

function FormField({
  label,
  children,
  required,
}: {
  label: string
  children: React.ReactNode
  required?: boolean
}) {
  return (
    <div className="space-y-1.5">
      <Label>
        {label}
        {required && <span className="text-destructive ml-0.5">*</span>}
      </Label>
      {children}
    </div>
  )
}

export default function MemberEditPage() {
  const { id } = useParams<{ id: string }>()
  const { data: member, isLoading } = useMember(id)

  if (isLoading || !member) {
    return (
      <div className="p-6 text-muted-foreground text-sm">Loading…</div>
    )
  }

  return <MemberEditForm id={id} member={member} />
}

function MemberEditForm({ id, member }: { id: string; member: Member }) {
  const router = useRouter()
  const { has } = usePermissions()
  const { data: groups = [] } = useGroups()
  const memberGroups = useMemberGroups(id)
  const { data: assignments = [] } = useMemberPositions(id)
  const { data: allPositions = [] } = usePositions()
  const { data: relationships = [] } = useRelationships(id)
  const { data: allMembers = [] } = useMembers()
  const updateMember = useUpdateMember()

  const [form, setForm] = useState<FormState>(() => toFormState(member))
  const [error, setError] = useState<string | null>(null)

  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  function handleText(key: keyof FormState) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      set(key, e.target.value as FormState[typeof key])
  }

  async function handleSave() {
    if (!form.first_name.trim() || !form.last_name.trim()) {
      setError("First name and last name are required.")
      return
    }
    setError(null)
    updateMember.mutate(
      { id, data: toApiPayload(form) },
      { onSuccess: () => router.push("/members") },
    )
  }

  const displayName = `${member.first_name} ${member.last_name}`

  return (
    <>
      <PageHeader title={`Edit — ${displayName}`}>
        <Button variant="outline" onClick={() => router.push("/members")}>
          Cancel
        </Button>
        <Button onClick={handleSave} disabled={updateMember.isPending}>
          {updateMember.isPending ? "Saving…" : "Save"}
        </Button>
      </PageHeader>

      <div className="max-w-2xl mx-auto p-4 md:p-6 space-y-6">
        {error && (
          <p className="text-sm text-destructive">{error}</p>
        )}
        {updateMember.isError && (
          <p className="text-sm text-destructive">
            Save failed — please try again.
          </p>
        )}

        {/* ── Identity ─────────────────────────────────────── */}
        <SectionTitle>Identity</SectionTitle>
        <div className="grid grid-cols-2 gap-4">
          <FormField label="First name" required>
            <Input value={form.first_name} onChange={handleText("first_name")} />
          </FormField>
          <FormField label="Last name" required>
            <Input value={form.last_name} onChange={handleText("last_name")} />
          </FormField>
          <FormField label="Middle name">
            <Input value={form.middle_name} onChange={handleText("middle_name")} />
          </FormField>
          <FormField label="Suffix">
            <Input value={form.name_suffix} onChange={handleText("name_suffix")} placeholder="Jr., Sr., III…" />
          </FormField>
          <FormField label="Nickname / preferred name">
            <Input value={form.nickname} onChange={handleText("nickname")} />
          </FormField>
          <FormField label="Date of birth">
            <Input type="date" value={form.date_of_birth} onChange={handleText("date_of_birth")} />
          </FormField>
          <FormField label="Member type" required>
            <Select
              value={form.member_type}
              onValueChange={(v) => set("member_type", v as MemberType)}
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
            <Input value={form.bsa_id} onChange={handleText("bsa_id")} />
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
            <Input type="date" value={form.swim_date} onChange={handleText("swim_date")} />
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
              />
              Active OA member
            </label>
            <FormField label="Election date">
              <Input type="date" value={form.oa_election_date} onChange={handleText("oa_election_date")} />
            </FormField>
            <FormField label="Call-out date">
              <Input type="date" value={form.oa_call_out_date} onChange={handleText("oa_call_out_date")} />
            </FormField>
            <FormField label="Ordeal date">
              <Input type="date" value={form.oa_ordeal_date} onChange={handleText("oa_ordeal_date")} />
            </FormField>
            <FormField label="Brotherhood date">
              <Input type="date" value={form.oa_brotherhood_date} onChange={handleText("oa_brotherhood_date")} />
            </FormField>
            <FormField label="Vigil date">
              <Input type="date" value={form.oa_vigil_date} onChange={handleText("oa_vigil_date")} />
            </FormField>
            <FormField label="Vigil name">
              <Input value={form.oa_vigil_name} onChange={handleText("oa_vigil_name")} />
            </FormField>
            <div className="col-span-2">
              <FormField label="OA notes">
                <Textarea value={form.oa_notes} onChange={handleText("oa_notes")} rows={2} />
              </FormField>
            </div>
          </div>
        )}

        <Separator />

        {/* ── Family ───────────────────────────────────────── */}
        <SectionTitle>Family</SectionTitle>
        <FamilyRelationshipsEditor
          memberId={id}
          relationships={relationships}
          allMembers={allMembers}
        />

        <Separator />

        {/* ── Groups & Patrols ─────────────────────────────── */}
        <SectionTitle>Groups &amp; Patrols</SectionTitle>
        <GroupMembershipEditor
          memberId={id}
          memberGroups={memberGroups}
          allGroups={groups}
        />

        <Separator />

        {/* ── Positions ────────────────────────────────────── */}
        <SectionTitle>Positions</SectionTitle>
        <MemberPositionsEditor
          memberId={id}
          assignments={assignments}
          allPositions={allPositions}
          canAssign={has("role:assign")}
        />

        <Separator />

        {/* ── Notes ────────────────────────────────────────── */}
        <SectionTitle>Notes</SectionTitle>
        <FormField label="Internal notes">
          <Textarea value={form.notes} onChange={handleText("notes")} rows={3} />
        </FormField>

        <div className="flex justify-end gap-3 pt-2">
          <Button variant="outline" onClick={() => router.push("/members")}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={updateMember.isPending}>
            {updateMember.isPending ? "Saving…" : "Save changes"}
          </Button>
        </div>
      </div>
    </>
  )
}
