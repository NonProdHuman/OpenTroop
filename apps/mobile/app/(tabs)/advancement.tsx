import { useColors } from "@/lib/theme"
import { useMemo, useState } from "react"
import {
  Modal,
  Pressable,
  RefreshControl,
  ScrollView,
  Text,
  TextInput,
  useColorScheme,
  View,
} from "react-native"
import {
  useAdvancementScouts,
  useMemberAdvancement,
  useMeritBadgeCatalog,
  useRecordCompletion,
  useTenantSettings,
} from "@/hooks/use-advancement"
import { useCachedPermissions, useCachedSession } from "@/hooks/use-mirror"
import { formatMemberName } from "@/lib/format"
import { LoadingScreen } from "@/components/loading-screen"
import type { AdvancementScout, MemberRankView, RequirementProgress } from "@/lib/types"

function today(): string {
  return new Date().toISOString().slice(0, 10)
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

/** Date-entry sheet: prefilled with today, editable as YYYY-MM-DD. */
function RecordSheet({
  entry,
  onConfirm,
  onClose,
  isRecorder,
}: {
  entry: RequirementProgress
  onConfirm: (date: string) => void
  onClose: () => void
  isRecorder: boolean
}) {
  const colors = useColors()
  const scheme = useColorScheme()
  const [date, setDate] = useState(today())
  const valid = /^\d{4}-\d{2}-\d{2}$/.test(date)
  return (
    <Modal transparent animationType="fade" onRequestClose={onClose}>
      <Pressable
        onPress={onClose}
        style={{
          flex: 1,
          backgroundColor: colors.overlay,
          justifyContent: "center",
          padding: 24,
        }}
      >
        <Pressable
          onPress={() => undefined}
          style={{ backgroundColor: colors.surface, borderRadius: 16, padding: 20, gap: 12 }}
        >
          <Text style={{ fontWeight: "700", fontSize: 16, color: colors.textStrong }}>
            {isRecorder ? "Mark complete" : "Report completion"} — {entry.requirement.label}
          </Text>
          <Text style={{ color: colors.text }} numberOfLines={4}>
            {entry.requirement.text}
          </Text>
          <Text style={{ color: colors.textMuted, fontSize: 12 }}>Date completed</Text>
          <TextInput
            value={date}
            onChangeText={setDate}
            placeholder="YYYY-MM-DD"
            placeholderTextColor={colors.textSubtle}
            autoCapitalize="none"
            keyboardAppearance={scheme === "dark" ? "dark" : "light"}
            style={{
              borderWidth: 1,
              borderColor: valid ? colors.border : colors.dangerInput,
              borderRadius: 8,
              padding: 10,
              color: colors.text,
              backgroundColor: colors.background,
            }}
          />
          <Pressable
            disabled={!valid}
            onPress={() => onConfirm(date)}
            style={{
              backgroundColor: valid ? colors.brand : colors.textSubtle,
              borderRadius: 8,
              padding: 12,
              alignItems: "center",
            }}
          >
            <Text style={{ color: colors.onBrand, fontWeight: "600" }}>
              {isRecorder ? "Record" : "Report"}
            </Text>
          </Pressable>
        </Pressable>
      </Pressable>
    </Modal>
  )
}

function RankSection({
  view,
  canWrite,
  isRecorder,
  onRecord,
}: {
  view: MemberRankView
  canWrite: boolean
  isRecorder: boolean
  onRecord: (entry: RequirementProgress) => void
}) {
  const colors = useColors()
  const [open, setOpen] = useState(false)
  const top = view.requirements.filter((r) => r.requirement.parent_id === null)
  const complete = top.filter((r) => r.is_complete).length
  const earned = view.progress?.completed_date != null
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
        </Text>
        <Text style={{ color: colors.textMuted }}>
          {complete}/{top.length} {open ? "▾" : "▸"}
        </Text>
      </Pressable>
      {open && (
        <View style={{ paddingHorizontal: 14, paddingBottom: 10 }}>
          {view.requirements.map((entry) => (
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
              <Text style={{ flex: 1, fontSize: 13, color: colors.text }}>
                {entry.requirement.text}
              </Text>
              {canWrite &&
                !entry.completion &&
                entry.metrics_progress.length === 0 &&
                !containerIds.has(entry.requirement.id) && (
                <Pressable onPress={() => onRecord(entry)}>
                  <Text style={{ color: colors.accent, fontWeight: "600" }}>
                    {isRecorder ? "Record" : "Report"}
                  </Text>
                </Pressable>
              )}
              {entry.completion && (
                <Text style={{ color: colors.textMuted, fontSize: 12 }}>
                  {entry.completion.status}
                </Text>
              )}
            </View>
          ))}
        </View>
      )}
    </View>
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
  const record = useRecordCompletion(scoutId ?? "")
  const [recording, setRecording] = useState<RequirementProgress | null>(null)

  const isRecorder = has("advancement:record")
  const canSelfReport =
    settings?.advancement_mode === "scout_reported" &&
    (session?.member?.id === scoutId || !has("advancement:read"))
  const canWrite = Boolean(scoutId) && (isRecorder || Boolean(canSelfReport))

  const badges = useMemo(() => advancement?.merit_badges ?? [], [advancement])
  const { data: catalog = [] } = useMeritBadgeCatalog()
  const badgeName = useMemo(() => {
    const map = new Map(catalog.map((b) => [b.id, b.name]))
    return (id: string) => map.get(id) ?? "Merit badge"
  }, [catalog])

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
      refreshControl={
        <RefreshControl
          refreshing={isRefetching}
          onRefresh={() => refetch()}
          tintColor={colors.textMuted}
        />
      }
    >
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
          onRecord={setRecording}
        />
      ))}

      {advancement && (
        <View style={{ marginTop: 8 }}>
          <Text style={{ fontWeight: "700", marginBottom: 6, color: colors.textStrong }}>Merit badges</Text>
          {badges.length === 0 && (
            <Text style={{ color: colors.textMuted }}>No merit badge records yet.</Text>
          )}
          {badges.map((badge) => (
            <Text key={badge.id} style={{ color: colors.text, paddingVertical: 2 }}>
              • {badgeName(badge.merit_badge_id)}
              {"  ·  "}
              {badge.date_completed ? `completed ${badge.date_completed}` : "in progress"}
              {"  ·  "}
              {badge.status}
            </Text>
          ))}
        </View>
      )}

      {recording && scoutId && (
        <RecordSheet
          entry={recording}
          isRecorder={isRecorder}
          onClose={() => setRecording(null)}
          onConfirm={(date) => {
            record.mutate({ requirement_id: recording.requirement.id, date_completed: date })
            setRecording(null)
          }}
        />
      )}
    </ScrollView>
  )
}
