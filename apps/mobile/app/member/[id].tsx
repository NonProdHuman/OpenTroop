import { colors } from "@/lib/theme"
import { ScrollView, Text, View } from "react-native"
import { Stack, useLocalSearchParams } from "expo-router"
import { useMirrorMember } from "@/hooks/use-mirror"
import { formatMemberName } from "@/lib/format"

function Field({ label, value }: { label: string; value: string | null | undefined }) {
  if (!value) return null
  return (
    <View style={{ marginBottom: 10 }}>
      <Text style={{ color: colors.textMuted, fontSize: 12 }}>{label}</Text>
      <Text style={{ fontSize: 15 }}>{value}</Text>
    </View>
  )
}

/**
 * The at-camp lookup (GH-153 §C8 step 3): allergies, medical, and emergency
 * contacts straight from the local mirror — no signal required.
 */
export default function MemberDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>()
  const member = useMirrorMember(id)

  if (!member) {
    return (
      <>
        <Stack.Screen options={{ headerShown: true, title: "Member" }} />
        <Text style={{ padding: 24, color: colors.textMuted }}>
          This member isn&apos;t in your local data yet — sync when you have signal.
        </Text>
      </>
    )
  }

  const address = [member.address_line1, member.address_line2, member.city, member.state]
    .filter(Boolean)
    .join(", ")

  return (
    <>
      <Stack.Screen options={{ headerShown: true, title: formatMemberName(member) }} />
      <ScrollView contentContainerStyle={{ padding: 16 }}>
        <Text style={{ fontSize: 20, fontWeight: "700", marginBottom: 2 }}>
          {formatMemberName(member)}
        </Text>
        <Text style={{ color: colors.textMuted, marginBottom: 16 }}>
          {member.member_type}
          {member.membership_status !== "active" ? ` · ${member.membership_status}` : ""}
        </Text>

        <Field label="Phone" value={member.phone} />
        <Field label="Email" value={member.email} />
        <Field label="Address" value={address} />
        <Field label="Allergies" value={member.allergies} />
        <Field label="Dietary restrictions" value={member.dietary_restrictions} />
        <Field label="Medical form A/B" value={member.medical_form_ab_date} />
        <Field label="Medical form C" value={member.medical_form_c_date} />
        <Field label="Swim classification" value={member.swim_classification} />
        <Field
          label="Emergency contact 1"
          value={
            member.emergency_contact_1_name
              ? `${member.emergency_contact_1_name} — ${member.emergency_contact_1_phone ?? ""}`
              : null
          }
        />
        <Field
          label="Emergency contact 2"
          value={
            member.emergency_contact_2_name
              ? `${member.emergency_contact_2_name} — ${member.emergency_contact_2_phone ?? ""}`
              : null
          }
        />
        <Field label="Notes" value={member.notes} />
      </ScrollView>
    </>
  )
}
