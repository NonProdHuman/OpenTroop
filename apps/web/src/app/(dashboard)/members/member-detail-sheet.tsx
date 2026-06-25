"use client"

import { useRouter } from "next/navigation"
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import type { Member } from "@/types/api"
import { formatDate } from "@/lib/format"
import { useMemberRoleAssignments } from "@/hooks/use-role-assignments"
import { useRoles } from "@/hooks/use-roles"
import { useUpdateMember, useInviteMember } from "@/hooks/use-members"
import { Pencil, UserCheck, UserMinus, Mail } from "lucide-react"

interface MemberDetailSheetProps {
  member: Member | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  if (!value && value !== 0) return null
  return (
    <div className="grid grid-cols-3 gap-2 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="col-span-2">{value}</span>
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-3">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        {title}
      </h3>
      {children}
    </div>
  )
}

export function MemberDetailSheet({ member, open, onOpenChange }: MemberDetailSheetProps) {
  const router = useRouter()
  const { data: assignments = [] } = useMemberRoleAssignments(member?.id ?? null)
  const { data: roles = [] } = useRoles()
  const roleById = new Map(roles.map((r) => [r.id, r.name]))
  const updateMember = useUpdateMember()
  const inviteMember = useInviteMember()

  if (!member) return null

  const displayName = member.nickname
    ? `${member.first_name} "${member.nickname}" ${member.last_name}`
    : `${member.first_name} ${member.last_name}`

  const fullAddress = [
    member.address_line1,
    member.address_line2,
    member.city && member.state
      ? `${member.city}, ${member.state} ${member.postal_code ?? ""}`.trim()
      : member.city ?? member.state,
  ]
    .filter(Boolean)
    .join("\n")

  function handleEdit() {
    onOpenChange(false)
    router.push(`/members/${member!.id}/edit`)
  }

  function handleDeactivate() {
    updateMember.mutate({
      id: member!.id,
      data: {
        membership_status:
          member!.membership_status === "active" ? "inactive" : "active",
      },
    })
  }

  function handleInvite() {
    inviteMember.mutate(member!.id)
  }

  const isActive = member.membership_status === "active"
  const isClaimed = member.user_id !== null

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full sm:max-w-lg overflow-y-auto">
        <SheetHeader className="pb-4">
          <SheetTitle className="text-xl">{displayName}</SheetTitle>
          <SheetDescription className="sr-only">Member details</SheetDescription>
          <div className="flex items-center gap-2 mt-1">
            <Badge variant={member.member_type === "adult" ? "secondary" : "default"}>
              {member.member_type === "adult" ? "Adult" : "Scout"}
            </Badge>
            {member.membership_status !== "active" && (
              <Badge
                variant={member.membership_status === "alumni" ? "outline" : "secondary"}
              >
                {member.membership_status.charAt(0).toUpperCase() +
                  member.membership_status.slice(1)}
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-2 pt-1 flex-wrap">
            <Button size="sm" variant="outline" onClick={handleEdit}>
              <Pencil className="h-3.5 w-3.5 mr-1.5" />
              Edit
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={handleDeactivate}
              disabled={updateMember.isPending}
            >
              {isActive ? (
                <>
                  <UserMinus className="h-3.5 w-3.5 mr-1.5" />
                  Deactivate
                </>
              ) : (
                <>
                  <UserCheck className="h-3.5 w-3.5 mr-1.5" />
                  Reactivate
                </>
              )}
            </Button>
            {!isClaimed && (
              <Button
                size="sm"
                variant="outline"
                onClick={handleInvite}
                disabled={inviteMember.isPending}
              >
                <Mail className="h-3.5 w-3.5 mr-1.5" />
                Send Invite
              </Button>
            )}
          </div>
          {inviteMember.isSuccess && (
            <p className="text-xs text-muted-foreground pt-1">
              Invite token copied — share with member to claim their account.
            </p>
          )}
        </SheetHeader>

        <div className="space-y-6">
          <Section title="Contact">
            <Field label="Email" value={member.email} />
            <Field label="Phone" value={member.phone} />
            {fullAddress && (
              <div className="grid grid-cols-3 gap-2 text-sm">
                <span className="text-muted-foreground">Address</span>
                <span className="col-span-2 whitespace-pre-line">{fullAddress}</span>
              </div>
            )}
            <Field label="BSA ID" value={member.bsa_id} />
            <Field label="Date of Birth" value={formatDate(member.date_of_birth)} />
          </Section>

          {(member.emergency_contact_1_name || member.emergency_contact_2_name) && (
            <>
              <Separator />
              <Section title="Emergency Contacts">
                {member.emergency_contact_1_name && (
                  <div className="space-y-1">
                    <Field label="Contact 1" value={member.emergency_contact_1_name} />
                    <Field label="" value={member.emergency_contact_1_phone} />
                  </div>
                )}
                {member.emergency_contact_2_name && (
                  <div className="space-y-1">
                    <Field label="Contact 2" value={member.emergency_contact_2_name} />
                    <Field label="" value={member.emergency_contact_2_phone} />
                  </div>
                )}
              </Section>
            </>
          )}

          {(member.medical_form_ab_date ||
            member.medical_form_c_date ||
            member.swim_classification ||
            member.allergies ||
            member.dietary_restrictions) && (
            <>
              <Separator />
              <Section title="Medical">
                <Field label="Form A/B" value={formatDate(member.medical_form_ab_date)} />
                <Field label="Form C" value={formatDate(member.medical_form_c_date)} />
                <Field label="Swim" value={member.swim_classification} />
                <Field label="Swim date" value={formatDate(member.swim_date)} />
                <Field label="Allergies" value={member.allergies} />
                <Field label="Dietary" value={member.dietary_restrictions} />
              </Section>
            </>
          )}

          {member.oa_member && (
            <>
              <Separator />
              <Section title="Order of the Arrow">
                <Field label="Active" value={member.oa_active ? "Yes" : "No"} />
                <Field label="Election" value={formatDate(member.oa_election_date)} />
                <Field label="Call-out" value={formatDate(member.oa_call_out_date)} />
                <Field label="Ordeal" value={formatDate(member.oa_ordeal_date)} />
                <Field label="Brotherhood" value={formatDate(member.oa_brotherhood_date)} />
                <Field label="Vigil" value={formatDate(member.oa_vigil_date)} />
                <Field label="Vigil name" value={member.oa_vigil_name} />
                {member.oa_notes && <Field label="Notes" value={member.oa_notes} />}
              </Section>
            </>
          )}

          {assignments.length > 0 && (
            <>
              <Separator />
              <Section title="Roles">
                <div className="flex flex-wrap gap-1.5">
                  {assignments.map((a) => {
                    const name = roleById.get(a.role_id)
                    return name ? (
                      <Badge key={a.id} variant="outline">
                        {name}
                      </Badge>
                    ) : null
                  })}
                </div>
              </Section>
            </>
          )}

          {(member.troop_membership_start_date || member.notes) && (
            <>
              <Separator />
              <Section title="Troop">
                <Field
                  label="Joined"
                  value={formatDate(member.troop_membership_start_date)}
                />
                <Field
                  label="Left"
                  value={formatDate(member.troop_membership_end_date)}
                />
                {member.notes && <Field label="Notes" value={member.notes} />}
              </Section>
            </>
          )}
        </div>
      </SheetContent>
    </Sheet>
  )
}
