import { useColors } from "@/lib/theme"
import { useMemo, useState } from "react"
import {
  Alert,
  Modal,
  Pressable,
  RefreshControl,
  ScrollView,
  Text,
  TextInput,
  useColorScheme,
  View,
  type TextInputProps,
} from "react-native"
import {
  useAdvancementQueue,
  useAdvancementScouts,
  useMemberAdvancement,
  useMeritBadgeCatalog,
  useRecordCompletion,
  useRecordMeritBadge,
  useRevokeCompletion,
  useTenantSettings,
  useUpdateCompletion,
  useUpdateMeritBadge,
  useUpdateRankProgress,
} from "@/hooks/use-advancement"
import { useCachedPermissions, useCachedSession } from "@/hooks/use-mirror"
import { formatMemberName } from "@/lib/format"
import { LoadingScreen } from "@/components/loading-screen"
import {
  availableBadges,
  buildCompletionPayload,
  buildMeritBadgePayload,
  buildMeritBadgeUpdate,
  buildRankDatesPayload,
  completionActions,
  filterBadgeCatalog,
  isValidDate,
  pendingCompletions,
  pendingMeritBadges,
  pendingQueueCount,
} from "@/lib/advancement"
import type {
  AdvancementScout,
  CompletionStatus,
  MemberMeritBadge,
  MemberRankView,
  MeritBadge,
  RequirementProgress,
} from "@/lib/types"

function today(): string {
  return new Date().toISOString().slice(0, 10)
}

/** Themed single-line input matching the dark-mode discipline (color, placeholder,
 *  border/background, keyboard appearance). */
function ThemedInput({ invalid, style, ...rest }: TextInputProps & { invalid?: boolean }) {
  const colors = useColors()
  const scheme = useColorScheme()
  return (
    <TextInput
      placeholderTextColor={colors.textSubtle}
      keyboardAppearance={scheme === "dark" ? "dark" : "light"}
      {...rest}
      style={[
        {
          borderWidth: 1,
          borderColor: invalid ? colors.dangerInput : colors.border,
          backgroundColor: colors.surface,
          color: colors.text,
          borderRadius: 8,
          padding: 10,
        },
        style,
      ]}
    />
  )
}

/** Modal shell used by every editor sheet — scrim + centered card. */
function Sheet({ onClose, children }: { onClose: () => void; children: React.ReactNode }) {
  const colors = useColors()
  return (
    <Modal transparent animationType="fade" onRequestClose={onClose}>
      <Pressable
        onPress={onClose}
        style={{ flex: 1, backgroundColor: colors.overlay, justifyContent: "center", padding: 24 }}
      >
        <Pressable
          onPress={() => undefined}
          style={{ backgroundColor: colors.surface, borderRadius: 16, padding: 20, gap: 12 }}
        >
          {children}
        </Pressable>
      </Pressable>
    </Modal>
  )
}

/** Primary action button. */
function PrimaryButton({
  label,
  onPress,
  disabled,
}: {
  label: string
  onPress: () => void
  disabled?: boolean
}) {
  const colors = useColors()
  return (
    <Pressable
      disabled={disabled}
      onPress={onPress}
      style={{
        backgroundColor: disabled ? colors.textSubtle : colors.brand,
        borderRadius: 8,
        padding: 12,
        alignItems: "center",
      }}
    >
      <Text style={{ color: colors.onBrand, fontWeight: "600" }}>{label}</Text>
    </Pressable>
  )
}

/** Scout chips — the permission-scoped picker (leaders: all; parents: wards; scouts: self). */
function ScoutChips({
  scouts,
  selectedId,
  onSelect,
}: {
  scouts: AdvancementScout[]
  selectedId: string | null
  onSelect: (id: string) => void
}) {
  const colors = useColors()
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ flexGrow: 0 }}>
      <View style={{ flexDirection: "row", gap: 8, paddingBottom: 8 }}>
        {scouts.map((scout) => {
          const active = scout.member_id === selectedId
          return (
            <Pressable
              key={scout.member_id}
              onPress={() => onSelect(scout.member_id)}
              style={{
                paddingHorizontal: 12,
                paddingVertical: 8,
                borderRadius: 999,
                borderWidth: 1,
                borderColor: active ? colors.accent : colors.border,
                backgroundColor: active ? colors.accentTint : colors.surface,
              }}
            >
              <Text style={{ color: active ? colors.accent : colors.text, fontWeight: "600" }}>
                {formatMemberName(scout)}
              </Text>
              <Text style={{ color: colors.textMuted, fontSize: 11 }}>
                {scout.current_rank_name ?? "No rank yet"}
              </Text>
            </Pressable>
          )
        })}
      </View>
    </ScrollView>
  )
}

/** Record/report a requirement completion — editable date plus an optional note. */
function RecordSheet({
  entry,
  onConfirm,
  onClose,
  isRecorder,
}: {
  entry: RequirementProgress
  onConfirm: (date: string, note: string) => void
  onClose: () => void
  isRecorder: boolean
}) {
  const colors = useColors()
  const [date, setDate] = useState(today())
  const [note, setNote] = useState("")
  const valid = isValidDate(date)
  return (
    <Sheet onClose={onClose}>
      <Text style={{ fontWeight: "700", fontSize: 16, color: colors.textStrong }}>
        {isRecorder ? "Mark complete" : "Report completion"} — {entry.requirement.label}
      </Text>
      <Text style={{ color: colors.text }} numberOfLines={4}>
        {entry.requirement.text}
      </Text>
      <Text style={{ color: colors.textMuted, fontSize: 12 }}>Date completed</Text>
      <ThemedInput
        value={date}
        onChangeText={setDate}
        placeholder="YYYY-MM-DD"
        autoCapitalize="none"
        invalid={!valid}
      />
      <Text style={{ color: colors.textMuted, fontSize: 12 }}>Note (optional)</Text>
      <ThemedInput
        value={note}
        onChangeText={setNote}
        placeholder="Add context for this completion…"
        multiline
        style={{ minHeight: 60, textAlignVertical: "top" }}
      />
      <PrimaryButton
        label={isRecorder ? "Record" : "Report"}
        disabled={!valid}
        onPress={() => onConfirm(date, note)}
      />
    </Sheet>
  )
}

/** Set/clear a rank's board-of-review (completed) and Court-of-Honor (awarded) dates. */
function RankDatesSheet({
  view,
  onConfirm,
  onClose,
}: {
  view: MemberRankView
  onConfirm: (completedDate: string, awardedDate: string) => void
  onClose: () => void
}) {
  const colors = useColors()
  const [completed, setCompleted] = useState(view.progress?.completed_date ?? "")
  const [awarded, setAwarded] = useState(view.progress?.awarded_date ?? "")
  const validCompleted = completed === "" || isValidDate(completed)
  const validAwarded = awarded === "" || isValidDate(awarded)
  return (
    <Sheet onClose={onClose}>
      <Text style={{ fontWeight: "700", fontSize: 16, color: colors.textStrong }}>
        {view.rank.name} dates
      </Text>
      <Text style={{ color: colors.textMuted, fontSize: 12 }}>
        Board of review (completed) — clear to reopen
      </Text>
      <ThemedInput
        value={completed}
        onChangeText={setCompleted}
        placeholder="YYYY-MM-DD"
        autoCapitalize="none"
        invalid={!validCompleted}
      />
      <Text style={{ color: colors.textMuted, fontSize: 12 }}>Awarded (Court of Honor)</Text>
      <ThemedInput
        value={awarded}
        onChangeText={setAwarded}
        placeholder="YYYY-MM-DD"
        autoCapitalize="none"
        invalid={!validAwarded}
      />
      <PrimaryButton
        label="Save dates"
        disabled={!validCompleted || !validAwarded}
        onPress={() => onConfirm(completed, awarded)}
      />
    </Sheet>
  )
}

/** Merit badge catalog picker (search) + optional completion date. */
function AddBadgeSheet({
  catalog,
  isRecorder,
  onConfirm,
  onClose,
}: {
  catalog: MeritBadge[]
  isRecorder: boolean
  onConfirm: (meritBadgeId: string, date: string) => void
  onClose: () => void
}) {
  const colors = useColors()
  const [query, setQuery] = useState("")
  const [selected, setSelected] = useState<string | null>(null)
  const [date, setDate] = useState(today())
  const results = useMemo(() => filterBadgeCatalog(catalog, query).slice(0, 30), [catalog, query])
  const validDate = date === "" || isValidDate(date)
  return (
    <Sheet onClose={onClose}>
      <Text style={{ fontWeight: "700", fontSize: 16, color: colors.textStrong }}>
        {isRecorder ? "Record a merit badge" : "Report a merit badge"}
      </Text>
      <ThemedInput
        value={query}
        onChangeText={setQuery}
        placeholder="Search merit badges…"
        autoCapitalize="none"
      />
      <ScrollView style={{ maxHeight: 220 }} keyboardShouldPersistTaps="handled">
        {results.map((badge) => {
          const active = badge.id === selected
          return (
            <Pressable
              key={badge.id}
              onPress={() => setSelected(badge.id)}
              style={{
                paddingVertical: 10,
                paddingHorizontal: 10,
                borderRadius: 8,
                backgroundColor: active ? colors.accentTint : "transparent",
              }}
            >
              <Text style={{ color: active ? colors.accent : colors.text, fontWeight: active ? "600" : "400" }}>
                {badge.name}
                {badge.eagle_required ? " ★" : ""}
              </Text>
            </Pressable>
          )
        })}
        {results.length === 0 && (
          <Text style={{ color: colors.textMuted, padding: 10 }}>No matching badges.</Text>
        )}
      </ScrollView>
      <Text style={{ color: colors.textMuted, fontSize: 12 }}>Date completed (optional)</Text>
      <ThemedInput
        value={date}
        onChangeText={setDate}
        placeholder="YYYY-MM-DD"
        autoCapitalize="none"
        invalid={!validDate}
      />
      <PrimaryButton
        label={isRecorder ? "Record" : "Report"}
        disabled={!selected || !validDate}
        onPress={() => selected && onConfirm(selected, date)}
      />
    </Sheet>
  )
}

/** Edit an existing merit badge record: completion date (clear to reopen) + status. */
function EditBadgeSheet({
  badge,
  badgeName,
  canApprove,
  onConfirm,
  onClose,
}: {
  badge: MemberMeritBadge
  badgeName: string
  canApprove: boolean
  onConfirm: (date: string, status?: "approved" | "rejected") => void
  onClose: () => void
}) {
  const colors = useColors()
  const [date, setDate] = useState(badge.date_completed ?? "")
  const valid = date === "" || isValidDate(date)
  return (
    <Sheet onClose={onClose}>
      <Text style={{ fontWeight: "700", fontSize: 16, color: colors.textStrong }}>{badgeName}</Text>
      <Text style={{ color: colors.textMuted, fontSize: 12 }}>
        Date completed — clear to mark in progress
      </Text>
      <ThemedInput
        value={date}
        onChangeText={setDate}
        placeholder="YYYY-MM-DD"
        autoCapitalize="none"
        invalid={!valid}
      />
      <PrimaryButton label="Save" disabled={!valid} onPress={() => onConfirm(date)} />
      {canApprove && badge.status === "reported" && (
        <View style={{ flexDirection: "row", gap: 8 }}>
          <Pressable
            onPress={() => onConfirm(date, "approved")}
            style={{ flex: 1, borderWidth: 1, borderColor: colors.border, borderRadius: 8, padding: 10, alignItems: "center" }}
          >
            <Text style={{ color: colors.success, fontWeight: "600" }}>Approve</Text>
          </Pressable>
          <Pressable
            onPress={() => onConfirm(date, "rejected")}
            style={{ flex: 1, borderWidth: 1, borderColor: colors.border, borderRadius: 8, padding: 10, alignItems: "center" }}
          >
            <Text style={{ color: colors.danger, fontWeight: "600" }}>Reject</Text>
          </Pressable>
        </View>
      )}
    </Sheet>
  )
}

/** Inline approve/reject/revoke controls for a requirement completion. */
function CompletionActions({
  status,
  canApprove,
  canRecord,
  locked,
  onApprove,
  onReject,
  onRevoke,
}: {
  status: CompletionStatus
  canApprove: boolean
  canRecord: boolean
  locked: boolean
  onApprove: () => void
  onReject: () => void
  onRevoke: () => void
}) {
  const colors = useColors()
  const { showApproveReject, showRevoke } = completionActions({ status, canApprove, canRecord, locked })
  return (
    <View style={{ flexDirection: "row", gap: 10, alignItems: "center" }}>
      {showApproveReject && (
        <>
          <Pressable onPress={onApprove}>
            <Text style={{ color: colors.success, fontWeight: "600" }}>Approve</Text>
          </Pressable>
          <Pressable onPress={onReject}>
            <Text style={{ color: colors.danger, fontWeight: "600" }}>Reject</Text>
          </Pressable>
        </>
      )}
      {showRevoke && (
        <Pressable onPress={onRevoke}>
          <Text style={{ color: colors.danger }}>Revoke</Text>
        </Pressable>
      )}
    </View>
  )
}

function RankSection({
  view,
  canWrite,
  isRecorder,
  canApprove,
  canSelfReport,
  onRecord,
  onEditDates,
  onApprove,
  onReject,
  onRevoke,
}: {
  view: MemberRankView
  canWrite: boolean
  isRecorder: boolean
  canApprove: boolean
  canSelfReport: boolean
  onRecord: (entry: RequirementProgress) => void
  onEditDates: (view: MemberRankView) => void
  onApprove: (completionId: string) => void
  onReject: (completionId: string) => void
  onRevoke: (completionId: string, label: string) => void
}) {
  const colors = useColors()
  const [open, setOpen] = useState(false)
  const top = view.requirements.filter((r) => r.requirement.parent_id === null)
  const complete = top.filter((r) => r.is_complete).length
  const earned = view.progress?.completed_date != null
  const awarded = view.progress?.awarded_date != null
  // Containers derive from their children — the API refuses direct completion.
  const containerIds = new Set(
    view.requirements
      .map((r) => r.requirement.parent_id)
      .filter((id): id is string => id !== null),
  )

  return (
    <View style={{ borderWidth: 1, borderColor: colors.borderLight, borderRadius: 12, marginBottom: 10 }}>
      <Pressable
        onPress={() => setOpen((o) => !o)}
        style={{ padding: 14, flexDirection: "row", justifyContent: "space-between" }}
      >
        <Text style={{ fontWeight: "700", color: colors.textStrong }}>
          {view.rank.name}
          {earned ? `  ·  earned ${view.progress?.completed_date}` : ""}
          {awarded ? `  ·  awarded ${view.progress?.awarded_date}` : ""}
        </Text>
        <Text style={{ color: colors.textMuted }}>
          {complete}/{top.length} {open ? "▾" : "▸"}
        </Text>
      </Pressable>
      {open && (
        <View style={{ paddingHorizontal: 14, paddingBottom: 10 }}>
          {isRecorder && (
            <Pressable onPress={() => onEditDates(view)} style={{ paddingVertical: 6 }}>
              <Text style={{ color: colors.accent, fontWeight: "600" }}>Set BOR / awarded dates</Text>
            </Pressable>
          )}
          {view.requirements.map((entry) => {
            const completion = entry.completion
            const mayRecord =
              canWrite &&
              !awarded &&
              !completion &&
              entry.metrics_progress.length === 0 &&
              !containerIds.has(entry.requirement.id) &&
              (isRecorder || (canSelfReport && !earned))
            return (
              <View
                key={entry.requirement.id}
                style={{
                  flexDirection: "row",
                  alignItems: "flex-start",
                  gap: 8,
                  paddingVertical: 6,
                  paddingLeft: entry.requirement.letter ? 16 : 0,
                  borderTopWidth: 1,
                  borderColor: colors.hairline,
                }}
              >
                <Text
                  style={{
                    fontWeight: "700",
                    color: entry.is_complete ? colors.success : colors.textSubtle,
                    width: 34,
                  }}
                >
                  {entry.is_complete ? "✓" : ""} {entry.requirement.label}
                </Text>
                <View style={{ flex: 1, gap: 4 }}>
                  <Text style={{ fontSize: 13, color: colors.text }}>{entry.requirement.text}</Text>
                  {completion && (
                    <Text style={{ color: colors.textMuted, fontSize: 12 }}>
                      {completion.status}
                      {completion.recorded_via === "auto" ? " · auto" : ""}
                      {completion.date_completed ? `  ·  ${completion.date_completed}` : ""}
                      {completion.note ? `  ·  ${completion.note}` : ""}
                    </Text>
                  )}
                  {completion && (
                    <CompletionActions
                      status={completion.status}
                      canApprove={canApprove}
                      canRecord={isRecorder}
                      locked={awarded}
                      onApprove={() => onApprove(completion.id)}
                      onReject={() => onReject(completion.id)}
                      onRevoke={() => onRevoke(completion.id, entry.requirement.label)}
                    />
                  )}
                </View>
                {mayRecord && (
                  <Pressable onPress={() => onRecord(entry)}>
                    <Text style={{ color: colors.accent, fontWeight: "600" }}>
                      {isRecorder ? "Record" : "Report"}
                    </Text>
                  </Pressable>
                )}
              </View>
            )
          })}
        </View>
      )}
    </View>
  )
}

/** The pending-approval queue for holders of `advancement:approve`. */
function QueueModal({
  scoutName,
  badgeName,
  onClose,
  onApproveCompletion,
  onRejectCompletion,
  onApproveBadge,
  onRejectBadge,
  queue,
}: {
  scoutName: (memberId: string) => string
  badgeName: (id: string) => string
  onClose: () => void
  onApproveCompletion: (id: string) => void
  onRejectCompletion: (id: string) => void
  onApproveBadge: (id: string) => void
  onRejectBadge: (id: string) => void
  queue: Parameters<typeof pendingCompletions>[0]
}) {
  const colors = useColors()
  const completions = pendingCompletions(queue)
  const badges = pendingMeritBadges(queue)
  return (
    <Modal transparent animationType="slide" onRequestClose={onClose}>
      <View style={{ flex: 1, backgroundColor: colors.background }}>
        <View
          style={{
            flexDirection: "row",
            justifyContent: "space-between",
            alignItems: "center",
            padding: 16,
            borderBottomWidth: 1,
            borderColor: colors.borderLight,
          }}
        >
          <Text style={{ fontWeight: "700", fontSize: 18, color: colors.textStrong }}>
            Needs approval
          </Text>
          <Pressable onPress={onClose}>
            <Text style={{ color: colors.accent, fontWeight: "600" }}>Done</Text>
          </Pressable>
        </View>
        <ScrollView contentContainerStyle={{ padding: 16, gap: 10 }}>
          {completions.length === 0 && badges.length === 0 && (
            <Text style={{ color: colors.textMuted }}>Nothing is waiting for approval.</Text>
          )}
          {completions.map((c) => (
            <View
              key={c.id}
              style={{ borderWidth: 1, borderColor: colors.borderLight, borderRadius: 10, padding: 12, gap: 6 }}
            >
              <Text style={{ fontWeight: "600", color: colors.textStrong }}>{scoutName(c.member_id)}</Text>
              <Text style={{ color: colors.textMuted, fontSize: 12 }}>
                Requirement completion  ·  {c.date_completed}
                {c.note ? `  ·  ${c.note}` : ""}
              </Text>
              <View style={{ flexDirection: "row", gap: 16 }}>
                <Pressable onPress={() => onApproveCompletion(c.id)}>
                  <Text style={{ color: colors.success, fontWeight: "600" }}>Approve</Text>
                </Pressable>
                <Pressable onPress={() => onRejectCompletion(c.id)}>
                  <Text style={{ color: colors.danger, fontWeight: "600" }}>Reject</Text>
                </Pressable>
              </View>
            </View>
          ))}
          {badges.map((b) => (
            <View
              key={b.id}
              style={{ borderWidth: 1, borderColor: colors.borderLight, borderRadius: 10, padding: 12, gap: 6 }}
            >
              <Text style={{ fontWeight: "600", color: colors.textStrong }}>{scoutName(b.member_id)}</Text>
              <Text style={{ color: colors.textMuted, fontSize: 12 }}>
                {badgeName(b.merit_badge_id)}
                {b.date_completed ? `  ·  ${b.date_completed}` : ""}
              </Text>
              <View style={{ flexDirection: "row", gap: 16 }}>
                <Pressable onPress={() => onApproveBadge(b.id)}>
                  <Text style={{ color: colors.success, fontWeight: "600" }}>Approve</Text>
                </Pressable>
                <Pressable onPress={() => onRejectBadge(b.id)}>
                  <Text style={{ color: colors.danger, fontWeight: "600" }}>Reject</Text>
                </Pressable>
              </View>
            </View>
          ))}
        </ScrollView>
      </View>
    </Modal>
  )
}

export default function AdvancementScreen() {
  const colors = useColors()
  const { data: scouts, isLoading, error, refetch, isRefetching } = useAdvancementScouts()
  const [selected, setSelected] = useState<string | null>(null)
  const scoutId = selected ?? (scouts?.length === 1 ? scouts[0].member_id : null)
  const { data: advancement } = useMemberAdvancement(scoutId)
  const { data: settings } = useTenantSettings()
  const session = useCachedSession()
  const { has } = useCachedPermissions()

  const isRecorder = has("advancement:record")
  const canApprove = has("advancement:approve")
  const canSelfReport =
    settings?.advancement_mode === "scout_reported" &&
    (session?.member?.id === scoutId || !has("advancement:read"))
  const canWrite = Boolean(scoutId) && (isRecorder || Boolean(canSelfReport))

  const record = useRecordCompletion(scoutId ?? "")
  const updateCompletion = useUpdateCompletion()
  const revokeCompletion = useRevokeCompletion()
  const recordBadge = useRecordMeritBadge(scoutId ?? "")
  const updateBadge = useUpdateMeritBadge()
  const updateRank = useUpdateRankProgress(scoutId ?? "")
  const { data: queue } = useAdvancementQueue(canApprove)

  const [recording, setRecording] = useState<RequirementProgress | null>(null)
  const [rankDates, setRankDates] = useState<MemberRankView | null>(null)
  const [addingBadge, setAddingBadge] = useState(false)
  const [editingBadge, setEditingBadge] = useState<MemberMeritBadge | null>(null)
  const [queueOpen, setQueueOpen] = useState(false)

  const badges = useMemo(() => advancement?.merit_badges ?? [], [advancement])
  const { data: catalog = [] } = useMeritBadgeCatalog()
  const badgeName = useMemo(() => {
    const map = new Map(catalog.map((b) => [b.id, b.name]))
    return (id: string) => map.get(id) ?? "Merit badge"
  }, [catalog])
  const earnedIds = useMemo(() => new Set(badges.map((b) => b.merit_badge_id)), [badges])
  const badgePickList = useMemo(() => availableBadges(catalog, earnedIds), [catalog, earnedIds])
  const scoutName = useMemo(() => {
    const map = new Map((scouts ?? []).map((s) => [s.member_id, formatMemberName(s)]))
    return (id: string) => map.get(id) ?? "Scout"
  }, [scouts])
  const pendingCount = pendingQueueCount(queue)

  function confirmRevoke(id: string, label: string) {
    Alert.alert("Revoke completion?", `Remove the recorded completion for ${label}.`, [
      { text: "Cancel", style: "cancel" },
      { text: "Revoke", style: "destructive", onPress: () => revokeCompletion.mutate(id) },
    ])
  }

  if (isLoading) return <LoadingScreen />
  if (error) {
    return (
      <Text style={{ padding: 24, color: colors.textMuted }}>
        Advancement needs a connection — it isn&apos;t mirrored offline yet. Pull down on
        Events to check your signal, then come back.
      </Text>
    )
  }

  return (
    <ScrollView
      contentContainerStyle={{ padding: 16 }}
      refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={() => refetch()} />}
    >
      {canApprove && pendingCount > 0 && (
        <Pressable
          onPress={() => setQueueOpen(true)}
          style={{
            alignSelf: "flex-start",
            marginBottom: 10,
            paddingHorizontal: 12,
            paddingVertical: 8,
            borderRadius: 999,
            backgroundColor: colors.accentTint,
            borderWidth: 1,
            borderColor: colors.accent,
          }}
        >
          <Text style={{ color: colors.accent, fontWeight: "600" }}>
            Needs approval · {pendingCount}
          </Text>
        </Pressable>
      )}

      {scouts && scouts.length > 0 ? (
        <ScoutChips scouts={scouts} selectedId={scoutId} onSelect={setSelected} />
      ) : (
        <Text style={{ color: colors.textMuted }}>
          No scouts to show — advancement records for your family appear here once they are
          on the roster.
        </Text>
      )}

      {scoutId && !advancement && <LoadingScreen />}
      {advancement?.ranks.map((view) => (
        <RankSection
          key={view.rank.id}
          view={view}
          canWrite={canWrite}
          isRecorder={isRecorder}
          canApprove={canApprove}
          canSelfReport={Boolean(canSelfReport)}
          onRecord={setRecording}
          onEditDates={setRankDates}
          onApprove={(id) => updateCompletion.mutate({ id, data: { status: "approved" } })}
          onReject={(id) => updateCompletion.mutate({ id, data: { status: "rejected" } })}
          onRevoke={confirmRevoke}
        />
      ))}

      {advancement && (
        <View style={{ marginTop: 8 }}>
          <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
            <Text style={{ fontWeight: "700", color: colors.textStrong }}>Merit badges</Text>
            {canWrite && (
              <Pressable onPress={() => setAddingBadge(true)}>
                <Text style={{ color: colors.accent, fontWeight: "600" }}>Add</Text>
              </Pressable>
            )}
          </View>
          {badges.length === 0 && (
            <Text style={{ color: colors.textMuted }}>No merit badge records yet.</Text>
          )}
          {badges.map((badge) => (
            <Pressable
              key={badge.id}
              onPress={() => canWrite && setEditingBadge(badge)}
              style={{ paddingVertical: 4, flexDirection: "row", justifyContent: "space-between" }}
            >
              <Text style={{ color: colors.text, flex: 1 }}>
                • {badgeName(badge.merit_badge_id)}
                {"  ·  "}
                {badge.date_completed ? `completed ${badge.date_completed}` : "in progress"}
                {"  ·  "}
                {badge.status}
              </Text>
              {canWrite && (
                <Text style={{ color: colors.accent, fontWeight: "600" }}>Edit</Text>
              )}
            </Pressable>
          ))}
        </View>
      )}

      {recording && scoutId && (
        <RecordSheet
          entry={recording}
          isRecorder={isRecorder}
          onClose={() => setRecording(null)}
          onConfirm={(date, note) => {
            record.mutate(
              buildCompletionPayload({
                requirementId: recording.requirement.id,
                dateCompleted: date,
                note,
              }),
            )
            setRecording(null)
          }}
        />
      )}

      {rankDates && scoutId && (
        <RankDatesSheet
          view={rankDates}
          onClose={() => setRankDates(null)}
          onConfirm={(completedDate, awardedDate) => {
            updateRank.mutate({
              rankId: rankDates.rank.id,
              data: buildRankDatesPayload({ completedDate, awardedDate }),
            })
            setRankDates(null)
          }}
        />
      )}

      {addingBadge && scoutId && (
        <AddBadgeSheet
          catalog={badgePickList}
          isRecorder={isRecorder}
          onClose={() => setAddingBadge(false)}
          onConfirm={(meritBadgeId, date) => {
            recordBadge.mutate(buildMeritBadgePayload({ meritBadgeId, dateCompleted: date }))
            setAddingBadge(false)
          }}
        />
      )}

      {editingBadge && (
        <EditBadgeSheet
          badge={editingBadge}
          badgeName={badgeName(editingBadge.merit_badge_id)}
          canApprove={canApprove}
          onClose={() => setEditingBadge(null)}
          onConfirm={(date, status) => {
            updateBadge.mutate({
              id: editingBadge.id,
              data: buildMeritBadgeUpdate({ dateCompleted: date, status }),
            })
            setEditingBadge(null)
          }}
        />
      )}

      {queueOpen && (
        <QueueModal
          queue={queue}
          scoutName={scoutName}
          badgeName={badgeName}
          onClose={() => setQueueOpen(false)}
          onApproveCompletion={(id) => updateCompletion.mutate({ id, data: { status: "approved" } })}
          onRejectCompletion={(id) => updateCompletion.mutate({ id, data: { status: "rejected" } })}
          onApproveBadge={(id) => updateBadge.mutate({ id, data: { status: "approved" } })}
          onRejectBadge={(id) => updateBadge.mutate({ id, data: { status: "rejected" } })}
        />
      )}
    </ScrollView>
  )
}
