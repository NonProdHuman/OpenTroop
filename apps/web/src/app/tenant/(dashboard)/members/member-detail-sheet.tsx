"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { toast } from "sonner"
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
import { Field, Section } from "@/components/detail-helpers"
import type { Member } from "@/types/api"
import { formatDate } from "@/lib/format"
import { useMemberPositions } from "@/hooks/use-member-positions"
import { usePositions } from "@/hooks/use-positions"
import { useUpdateMember, useInviteMember } from "@/hooks/use-members"
import { Pencil, UserCheck, UserMinus, Mail, Copy, Check } from "lucide-react"

interface MemberDetailSheetProps {
  member: Member | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function MemberDetailSheet({ member, open, onOpenChange }: MemberDetailSheetProps) {
  const router = useRouter()
  const { data: assignments = [] } = useMemberPositions(member?.id ?? null)
  const { data: positions = [] } = usePositions()
  const positionById = new Map(positions.map((p) => [p.id, p.name]))
  const updateMember = useUpdateMember()
  const inviteMember = useInviteMember()
  const [copied, setCopied] = useState(false)

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
    setCopied(false)
    inviteMember.mutate(member!.id)
  }

  async function handleCopyClaimLink() {
    if (!inviteMember.data) return
    const claimUrl = `${window.location.origin}/claim?token=${inviteMember.data.token}`
    try {
      await navigator.clipboard.writeText(claimUrl)
      setCopied(true)
      toast.success("Invite link copied")
    } catch {
      toast.error("Couldn't copy — select and copy manually")
    }
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
          {inviteMember.isSuccess && inviteMember.data.email_sent && (
            <p className="text-xs text-muted-foreground pt-1">
              Invite email sent to {member.email} — they can use it to claim their account.
            </p>
          )}
          {inviteMember.isSuccess && !inviteMember.data.email_sent && (
            <div className="flex items-center gap-2 pt-1">
              <p className="text-xs text-muted-foreground">
                Couldn&apos;t email this invite — copy the link and share it manually.
              </p>
              <Button size="sm" variant="outline" onClick={handleCopyClaimLink}>
                {copied ? (
                  <Check className="h-3.5 w-3.5 mr-1.5" />
                ) : (
                  <Copy className="h-3.5 w-3.5 mr-1.5" />
                )}
                {copied ? "Copied" : "Copy link"}
              </Button>
            </div>
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
              <Section title="Positions">
                <div className="flex flex-wrap gap-1.5">
                  {assignments.map((a) => {
                    const name = positionById.get(a.position_id)
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
