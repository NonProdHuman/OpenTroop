import { useCallback, useMemo, useState } from "react"
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Modal,
  Pressable,
  Text,
  useWindowDimensions,
  View,
} from "react-native"
import { Stack, useLocalSearchParams } from "expo-router"
import { FlashList } from "@shopify/flash-list"
import { Image } from "expo-image"
import * as ImagePicker from "expo-image-picker"
import * as MediaLibrary from "expo-media-library"
import { downloadAsync, cacheDirectory } from "expo-file-system/legacy"
import { useColors } from "@/lib/theme"
import { useApiRequest } from "@/lib/api"
import { useCachedPermissions, useCachedSession } from "@/hooks/use-mirror"
import {
  useDeletePhoto,
  useDownloadUrl,
  useEventPhotos,
  useStorageUsage,
} from "@/hooks/use-event-photos"
import { bindNativePipeline, uploadPhotos, type UploadProgress } from "@/lib/photo-upload"
import type { EventPhoto } from "@/lib/types"

const GRID_COLUMNS = 3
const PICK_LIMIT = 30

function formatBytes(n: number): string {
  if (n >= 1024 ** 3) return `${(n / 1024 ** 3).toFixed(1)} GB`
  if (n >= 1024 ** 2) return `${(n / 1024 ** 2).toFixed(0)} MB`
  return `${Math.max(1, Math.round(n / 1024))} KB`
}

/** Full-screen swipe-between viewer with save / delete. */
function PhotoViewer({
  photos,
  initialIndex,
  canDelete,
  onDelete,
  onClose,
}: {
  photos: EventPhoto[]
  initialIndex: number
  canDelete: (photo: EventPhoto) => boolean
  onDelete: (photo: EventPhoto) => void
  onClose: () => void
}) {
  const { width, height } = useWindowDimensions()
  const [index, setIndex] = useState(initialIndex)
  const [saving, setSaving] = useState(false)
  const downloadUrl = useDownloadUrl()
  const photo = photos[index]

  const save = useCallback(async () => {
    if (!photo || saving) return
    setSaving(true)
    try {
      const permission = await MediaLibrary.requestPermissionsAsync(true)
      if (!permission.granted) {
        Alert.alert("Photos access needed", "Allow adding photos to save them to your library.")
        return
      }
      // Gallery URLs expire quickly — mint a fresh presigned GET at save time,
      // download to app cache, then hand the file to the media library.
      const { url } = await downloadUrl(photo.id)
      const target = `${cacheDirectory}opentroop-${photo.id}.jpg`
      const result = await downloadAsync(url, target)
      await MediaLibrary.saveToLibraryAsync(result.uri)
      Alert.alert("Saved", "Photo added to your library.")
    } catch {
      Alert.alert("Save failed", "Please try again.")
    } finally {
      setSaving(false)
    }
  }, [downloadUrl, photo, saving])

  if (!photo) return null

  return (
    <Modal animationType="fade" onRequestClose={onClose}>
      <View style={{ flex: 1, backgroundColor: "#000" }}>
        <FlatList
          data={photos}
          horizontal
          pagingEnabled
          initialScrollIndex={initialIndex}
          getItemLayout={(_, i) => ({ length: width, offset: width * i, index: i })}
          onMomentumScrollEnd={(e) =>
            setIndex(Math.round(e.nativeEvent.contentOffset.x / width))
          }
          keyExtractor={(item) => item.id}
          renderItem={({ item }) => (
            <View style={{ width, height }}>
              <Image
                source={{ uri: item.display_url }}
                style={{ flex: 1 }}
                contentFit="contain"
                transition={100}
              />
            </View>
          )}
        />
        <View
          style={{
            position: "absolute",
            top: 56,
            left: 16,
            right: 16,
            flexDirection: "row",
            justifyContent: "space-between",
          }}
        >
          <Pressable onPress={onClose} hitSlop={12}>
            <Text style={{ color: "#fff", fontSize: 16, fontWeight: "600" }}>Close</Text>
          </Pressable>
          <Text style={{ color: "#fff" }}>
            {index + 1} / {photos.length}
          </Text>
        </View>
        <View
          style={{
            position: "absolute",
            bottom: 48,
            left: 16,
            right: 16,
            flexDirection: "row",
            justifyContent: "space-between",
          }}
        >
          <Pressable onPress={() => void save()} hitSlop={12} disabled={saving}>
            <Text style={{ color: "#fff", fontSize: 16 }}>
              {saving ? "Saving…" : "Save to device"}
            </Text>
          </Pressable>
          {canDelete(photo) && (
            <Pressable
              hitSlop={12}
              onPress={() =>
                Alert.alert("Remove photo?", "It will disappear from the event for everyone.", [
                  { text: "Cancel", style: "cancel" },
                  { text: "Remove", style: "destructive", onPress: () => onDelete(photo) },
                ])
              }
            >
              <Text style={{ color: "#ff6b6b", fontSize: 16 }}>Remove</Text>
            </Pressable>
          )}
        </View>
      </View>
    </Modal>
  )
}

export default function EventPhotosScreen() {
  const { id } = useLocalSearchParams<{ id: string }>()
  const colors = useColors()
  const { width } = useWindowDimensions()
  const api = useApiRequest()
  const session = useCachedSession()
  const { has } = useCachedPermissions()
  const photosQuery = useEventPhotos(id ?? null)
  const usage = useStorageUsage()
  const deletePhoto = useDeletePhoto(id ?? "")

  const [progress, setProgress] = useState<UploadProgress | null>(null)
  const [failures, setFailures] = useState(0)
  const [viewerIndex, setViewerIndex] = useState<number | null>(null)

  const photos = useMemo(() => photosQuery.data ?? [], [photosQuery.data])
  const tile = Math.floor((width - 4 * (GRID_COLUMNS + 1)) / GRID_COLUMNS)
  const myMemberId = session?.member?.id ?? null

  const canDelete = useCallback(
    (photo: EventPhoto) =>
      has("photo:moderate") || (myMemberId !== null && photo.uploaded_by_member_id === myMemberId),
    [has, myMemberId],
  )

  const pickAndUpload = useCallback(async () => {
    if (!id || progress) return
    // The modern limited-library sheet: users can grant access to just the
    // photos they pick. exif: false — location metadata never enters JS; the
    // manipulate step strips it from the pixels' container anyway.
    const picked = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ["images"],
      allowsMultipleSelection: true,
      selectionLimit: PICK_LIMIT,
      exif: false,
      quality: 1,
    })
    if (picked.canceled || picked.assets.length === 0) return

    setFailures(0)
    const deps = bindNativePipeline(api)
    const result = await uploadPhotos(
      deps,
      id,
      picked.assets.map((a) => ({ uri: a.uri, fileName: a.fileName })),
      (p) => setProgress(p),
    )
    setProgress(null)
    setFailures(result.failed)
    if (result.uploaded > 0) {
      void photosQuery.refetch()
      void usage.refetch()
    }
  }, [api, id, photosQuery, progress, usage])

  return (
    <>
      <Stack.Screen options={{ title: "Photos" }} />
      <View style={{ flex: 1, backgroundColor: colors.background }}>
        <View style={{ padding: 16, gap: 8 }}>
          <View
            style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}
          >
            {has("photo:upload") ? (
              <Pressable
                onPress={() => void pickAndUpload()}
                disabled={progress !== null}
                style={{
                  backgroundColor: colors.brand,
                  borderRadius: 8,
                  paddingHorizontal: 14,
                  paddingVertical: 8,
                  opacity: progress ? 0.6 : 1,
                }}
              >
                <Text style={{ color: colors.onBrand, fontWeight: "600" }}>
                  {progress
                    ? `Uploading ${progress.index + 1}/${progress.total}…`
                    : "Add photos"}
                </Text>
              </Pressable>
            ) : (
              <View />
            )}
            {usage.data && (
              <Text style={{ color: colors.textMuted, fontSize: 12 }}>
                {formatBytes(usage.data.remaining_bytes)} left
              </Text>
            )}
          </View>
          {failures > 0 && (
            <Text style={{ color: colors.danger, fontSize: 12 }}>
              {failures} photo{failures === 1 ? "" : "s"} failed to upload — try again.
            </Text>
          )}
        </View>

        {photosQuery.isLoading ? (
          <ActivityIndicator style={{ marginTop: 32 }} />
        ) : photosQuery.isError ? (
          <Text style={{ color: colors.textMuted, textAlign: "center", marginTop: 32 }}>
            Photos need a connection — try again online.
          </Text>
        ) : photos.length === 0 ? (
          <Text style={{ color: colors.textMuted, textAlign: "center", marginTop: 32 }}>
            No photos yet — be the first to add some.
          </Text>
        ) : (
          <FlashList
            data={photos}
            numColumns={GRID_COLUMNS}
            keyExtractor={(item) => item.id}
            renderItem={({ item, index }) => (
              <Pressable onPress={() => setViewerIndex(index)} style={{ padding: 2 }}>
                <Image
                  source={{ uri: item.display_url }}
                  placeholder={item.thumbhash ? { thumbhash: item.thumbhash } : undefined}
                  style={{ width: tile, height: tile, borderRadius: 6 }}
                  contentFit="cover"
                  recyclingKey={item.id}
                  transition={100}
                />
              </Pressable>
            )}
            contentContainerStyle={{ paddingHorizontal: 4, paddingBottom: 32 }}
          />
        )}
      </View>

      {viewerIndex !== null && (
        <PhotoViewer
          photos={photos}
          initialIndex={viewerIndex}
          canDelete={canDelete}
          onDelete={(photo) => {
            deletePhoto.mutate(photo.id)
            setViewerIndex(null)
          }}
          onClose={() => setViewerIndex(null)}
        />
      )}
    </>
  )
}
