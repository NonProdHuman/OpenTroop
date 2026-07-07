"use client"

import Link from "next/link"
import { Mail, Phone, Pencil } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { formatMemberName } from "@/lib/format"
import { cn } from "@/lib/utils"
import {
  MEDICAL_STATUS_CLASSES,
  medicalStatus,
  medicalStatusLabel,
} from "@/lib/medical-status"
import type { Member } from "@/types/api"

function MedicalChip({ label, formDate }: { label: string; formDate: string | null | undefined }) {
  const status = medicalStatus(formDate)
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium",
        MEDICAL_STATUS_CLASSES[status],
      )}
      data-testid={`medical-chip-${label.toLowerCase()}`}
      data-status={status}
    >
      {label}: {medicalStatusLabel(status)}
    </span>
  )
}

/** One household member: identity, contact summary, medical-form chips, Edit link. */
export function FamilyMemberCard({ member, patrolName }: { member: Member; patrolName?: string }) {
  return (
    <Card data-testid="family-member-card">
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="flex items-center gap-2 text-base">
            {formatMemberName(member)}
            <span className="text-xs font-normal capitalize text-muted-foreground">
              {member.member_type}
            </span>
            {patrolName && (
              <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-normal text-muted-foreground">
                {patrolName}
              </span>
            )}
          </CardTitle>
          <Button
            size="sm"
            variant="outline"
            render={<Link href={`/members/${member.id}/edit`} />}
            nativeButton={false}
          >
            <Pencil className="mr-1 h-3.5 w-3.5" />
            Edit
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-col gap-1 text-sm text-muted-foreground">
          {member.email && (
            <span className="flex items-center gap-2">
              <Mail className="h-3.5 w-3.5 shrink-0" />
              {member.email}
            </span>
          )}
          {member.phone && (
            <span className="flex items-center gap-2">
              <Phone className="h-3.5 w-3.5 shrink-0" />
              {member.phone}
            </span>
          )}
          {!member.email && !member.phone && (
            <span className="italic">No contact info on file</span>
          )}
        </div>
        <div className="flex flex-wrap gap-1.5">
          <MedicalChip label="A/B" formDate={member.medical_form_ab_date} />
          <MedicalChip label="C" formDate={member.medical_form_c_date} />
        </div>
      </CardContent>
    </Card>
  )
}
