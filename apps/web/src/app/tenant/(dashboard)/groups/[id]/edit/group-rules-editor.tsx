"use client"

import { useState } from "react"
import { SectionTitle } from "@/components/form-helpers"
import { MultiSelectChips } from "@/components/multi-select-chips"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { cn } from "@/lib/utils"
import {
  useDeleteGroupRule,
  useGroupRules,
  useGroups,
  useUpsertGroupRule,
} from "@/hooks/use-groups"
import { usePositions } from "@/hooks/use-positions"
import type { Group, RuleDimension, RuleLogic } from "@/types/api"

// Youth/adult hint for the position picker, derived from Position.applies_to.
function positionScopeLabel(scope: string): string | undefined {
  if (scope === "scout") return "Youth"
  if (scope === "adult") return "Adult"
  return undefined
}

// Dynamic-rule configuration for a custom group: one RuleRow per dimension,
// plus the logic-mode selector. Rule edits save immediately via the rule hooks;
// only the logic mode is lifted (it saves with the enclosing form).
export function GroupRulesEditor({
  group,
  ruleLogic,
  onRuleLogicChange,
}: {
  group: Group
  ruleLogic: RuleLogic
  onRuleLogicChange: (v: RuleLogic) => void
}) {
  const { data: rules = [] } = useGroupRules(group.id)
  const { data: allPositions = [] } = usePositions()
  const { data: allGroups = [] } = useGroups()
  const upsertRule = useUpsertGroupRule()
  const deleteRule = useDeleteGroupRule()

  // Local state to keep track of dimensions that have been checked (expanded) by the user
  // but do not yet have saved filters in the database.
  const [expandedDimensions, setExpandedDimensions] = useState<Set<RuleDimension>>(new Set())

  const activeRulesMap = new Map(rules.filter((r) => !r.is_deleted).map((r) => [r.dimension, r]))

  // Toggle rule for boolean dimensions (OA member/active) which do not require additional configuration
  function handleRuleToggle(dimension: RuleDimension, enabled: boolean) {
    if (enabled) {
      upsertRule.mutate({ groupId: group.id, dimension, values: [] })
    } else {
      deleteRule.mutate({ groupId: group.id, dimension })
    }
  }

  // Expand/collapse multi-select dimensions locally first before they select values
  function toggleExpandDimension(dimension: RuleDimension, checked: boolean) {
    if (checked) {
      setExpandedDimensions((prev) => {
        const next = new Set(prev)
        next.add(dimension)
        return next
      })
    } else {
      setExpandedDimensions((prev) => {
        const next = new Set(prev)
        next.delete(dimension)
        return next
      })
      if (activeRulesMap.has(dimension)) {
        deleteRule.mutate({ groupId: group.id, dimension })
      }
    }
  }

  // Helper to save rule values to the backend
  function handleRuleSave(dimension: RuleDimension, values: string[] | null) {
    upsertRule.mutate({ groupId: group.id, dimension, values })
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <SectionTitle>Dynamic Rules</SectionTitle>
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">Logic Mode:</span>
          <Select value={ruleLogic} onValueChange={(v) => onRuleLogicChange(v as RuleLogic)}>
            <SelectTrigger className="h-7 w-28 text-xs"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="and">ALL (AND)</SelectItem>
              <SelectItem value="or">ANY (OR)</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="space-y-3">
        {/* 1. Member Type Rule */}
        <RuleRow
          label="Filter by Member Type"
          enabled={activeRulesMap.has("member_type") || expandedDimensions.has("member_type")}
          onToggle={(checked) => toggleExpandDimension("member_type", checked)}
        >
          <div className="flex gap-4">
            {["scout", "adult"].map((t) => {
              const currentVals = activeRulesMap.get("member_type")?.values || []
              const checked = currentVals.includes(t)
              return (
                <label key={t} className="text-xs flex items-center gap-1.5 cursor-pointer capitalize">
                  <input
                    type="checkbox"
                    checked={checked}
                    className="h-3.5 w-3.5 rounded border-gray-300 text-primary focus:ring-primary"
                    onChange={() => {
                      const next = checked
                        ? currentVals.filter((x) => x !== t)
                        : [...currentVals, t]
                      if (next.length === 0) {
                        toggleExpandDimension("member_type", false)
                      } else {
                        handleRuleSave("member_type", next)
                      }
                    }}
                  />
                  {t}s
                </label>
              )
            })}
          </div>
        </RuleRow>

        {/* 2. Membership Status Rule */}
        <RuleRow
          label="Filter by Membership Status"
          enabled={activeRulesMap.has("membership_status") || expandedDimensions.has("membership_status")}
          onToggle={(checked) => toggleExpandDimension("membership_status", checked)}
        >
          <div className="flex gap-4">
            {["active", "inactive", "alumni"].map((s) => {
              const currentVals = activeRulesMap.get("membership_status")?.values || []
              const checked = currentVals.includes(s)
              return (
                <label key={s} className="text-xs flex items-center gap-1.5 cursor-pointer capitalize">
                  <input
                    type="checkbox"
                    checked={checked}
                    className="h-3.5 w-3.5 rounded border-gray-300 text-primary focus:ring-primary"
                    onChange={() => {
                      const next = checked
                        ? currentVals.filter((x) => x !== s)
                        : [...currentVals, s]
                      if (next.length === 0) {
                        toggleExpandDimension("membership_status", false)
                      } else {
                        handleRuleSave("membership_status", next)
                      }
                    }}
                  />
                  {s}
                </label>
              )
            })}
          </div>
        </RuleRow>

        {/* 3. Is OA Member */}
        <RuleRow
          label="Only Order of the Arrow Members"
          enabled={activeRulesMap.has("oa_member")}
          onToggle={(checked) => handleRuleToggle("oa_member", checked)}
        />

        {/* 4. Is OA Active */}
        <RuleRow
          label="Only Active Order of the Arrow Members"
          enabled={activeRulesMap.has("oa_active")}
          onToggle={(checked) => handleRuleToggle("oa_active", checked)}
        />

        {/* 5. Position Rule */}
        <RuleRow
          label="Filter by Position(s)"
          enabled={activeRulesMap.has("position") || expandedDimensions.has("position")}
          onToggle={(checked) => toggleExpandDimension("position", checked)}
        >
          <MultiSelectChips
            options={allPositions
              .filter((p) => !p.is_deleted)
              .map((p) => ({ id: p.id, label: p.name, badge: positionScopeLabel(p.applies_to) }))}
            selectedIds={activeRulesMap.get("position")?.values || []}
            onChange={(next) =>
              next.length === 0
                ? toggleExpandDimension("position", false)
                : handleRuleSave("position", next)
            }
            addLabel="Add position…"
            searchPlaceholder="Search positions…"
            emptyLabel="No positions found."
          />
        </RuleRow>

        {/* 6. Group Member Rule */}
        <RuleRow
          label="Filter by Group Membership"
          enabled={activeRulesMap.has("group_member") || expandedDimensions.has("group_member")}
          onToggle={(checked) => toggleExpandDimension("group_member", checked)}
        >
          <MultiSelectChips
            options={allGroups
              .filter((g) => g.id !== group.id && !g.is_deleted)
              .map((g) => ({ id: g.id, label: g.name }))}
            selectedIds={activeRulesMap.get("group_member")?.values || []}
            onChange={(next) =>
              next.length === 0
                ? toggleExpandDimension("group_member", false)
                : handleRuleSave("group_member", next)
            }
            addLabel="Add group…"
            searchPlaceholder="Search groups…"
            emptyLabel="No groups found."
          />
        </RuleRow>

        {/* 7. Rank Rule (Phase 2 - Disabled) */}
        <RuleRow
          label="Filter by Rank(s)"
          enabled={false}
          disabled={true}
          comingSoon={true}
          onToggle={() => {}}
        />
      </div>
    </div>
  )
}

interface RuleRowProps {
  label: string
  enabled: boolean
  onToggle: (checked: boolean) => void
  disabled?: boolean
  comingSoon?: boolean
  children?: React.ReactNode
}

function RuleRow({ label, enabled, onToggle, disabled, comingSoon, children }: RuleRowProps) {
  return (
    <div className="space-y-2 p-3 rounded-md border bg-muted/20">
      <div className="flex items-center justify-between">
        <label className={cn("text-sm font-medium flex items-center gap-2 cursor-pointer select-none", disabled && "opacity-50 cursor-not-allowed")}>
          <input
            type="checkbox"
            className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary cursor-pointer disabled:cursor-not-allowed"
            checked={enabled}
            disabled={disabled}
            onChange={(e) => onToggle(e.target.checked)}
          />
          <span>{label}</span>
          {comingSoon && <span className="text-xs text-muted-foreground font-normal">{comingSoon}</span>}
        </label>
      </div>
      {enabled && children && (
        <div className="pl-6 pt-1 space-y-2">
          {children}
        </div>
      )}
    </div>
  )
}

interface ParentToggleProps {
  label: string
  hint: string
  checked: boolean
  disabled?: boolean
  onChange: (checked: boolean) => void
}

export function ParentToggle({ label, hint, checked, disabled, onChange }: ParentToggleProps) {
  return (
    <label
      className={cn(
        "flex items-start gap-2 p-3 rounded-md border bg-muted/20 cursor-pointer select-none",
        disabled && "opacity-60 cursor-not-allowed",
      )}
    >
      <input
        type="checkbox"
        className="h-4 w-4 mt-0.5 rounded border-gray-300 text-primary focus:ring-primary cursor-pointer disabled:cursor-not-allowed"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span className="space-y-0.5">
        <span className="block text-sm font-medium">{label}</span>
        <span className="block text-xs text-muted-foreground font-normal">{hint}</span>
      </span>
    </label>
  )
}
