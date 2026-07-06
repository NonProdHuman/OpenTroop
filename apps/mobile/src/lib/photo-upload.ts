/**
 * The photo upload pipeline for mobile (GH-145 spec §§3–4, §11).
 *
 * pick → downscale + EXIF-strip (expo-image-manipulator re-encode; drops GPS —
 * never upload original bytes) → `initiate` (quota reservation + presigned PUT)
 * → PUT the file straight to object storage → `complete` (server HEAD-verifies
 * and settles the tenant meter).
 *
 * Written against injected primitives (`api`, `putFile`, `manipulate`) so the
 * sequencing, error isolation, and retry semantics are unit-testable in node —
 * the Expo modules are bound once in `bindNativePipeline()`.
 *
 * Uploads run sequentially: campout uploads happen on weak links, where one
 * transfer at a time beats several stalled ones. A per-file failure marks that
 * file and moves on. Note v1 is session-resumable only (in-flight retry, no
 * durable queue across app restarts — that follow-up is tracked on GH-145).
 */

export interface ProcessedAsset {
  uri: string
  width: number
  height: number
  byteLength: number
}

export interface PickedAsset {
  uri: string
  fileName?: string | null
}

export type UploadStatus = "processing" | "uploading" | "done" | "error"

export interface UploadProgress {
  index: number
  total: number
  status: UploadStatus
  fileName: string
  error?: string
}

export interface PipelineDeps {
  /** Tenant-bound JSON API call (useApiRequest shape). */
  api: <T>(path: string, init?: { method: string; body?: unknown }) => Promise<T>
  /** Downscale + re-encode (EXIF strip) an asset; returns the temp file facts. */
  manipulate: (uri: string) => Promise<ProcessedAsset>
  /** PUT a local file's bytes to a presigned URL; resolves the HTTP status. */
  putFile: (url: string, fileUri: string, contentType: string) => Promise<number>
}

interface InitiateResponse {
  uploads: { photo_id: string; upload_url: string; expires_in_seconds: number }[]
}

export async function uploadPhotos(
  deps: PipelineDeps,
  eventId: string,
  assets: PickedAsset[],
  onProgress?: (p: UploadProgress) => void,
): Promise<{ uploaded: number; failed: number }> {
  let uploaded = 0
  let failed = 0
  for (const [index, asset] of assets.entries()) {
    const fileName = asset.fileName ?? `photo-${index + 1}`
    const report = (status: UploadStatus, error?: string) =>
      onProgress?.({ index, total: assets.length, status, fileName, error })
    try {
      report("processing")
      const processed = await deps.manipulate(asset.uri)
      const initiated = await deps.api<InitiateResponse>(`/events/${eventId}/photos/initiate`, {
        method: "POST",
        body: {
          photos: [
            {
              content_type: "image/jpeg",
              byte_length: processed.byteLength,
              width: processed.width,
              height: processed.height,
            },
          ],
        },
      })
      const target = initiated.uploads[0]
      report("uploading")
      const status = await deps.putFile(target.upload_url, processed.uri, "image/jpeg")
      if (status < 200 || status >= 300) {
        throw new Error(`Storage upload failed (${status})`)
      }
      await deps.api(`/photos/${target.photo_id}/complete`, { method: "POST" })
      uploaded += 1
      report("done")
    } catch (error) {
      failed += 1
      report("error", error instanceof Error ? error.message : "Upload failed")
    }
  }
  return { uploaded, failed }
}

/** Bind the pipeline to the real Expo modules (kept out of unit tests). */
export function bindNativePipeline(
  api: PipelineDeps["api"],
  maxLongEdge = 2048,
): Omit<PipelineDeps, "api"> & { api: PipelineDeps["api"] } {
  return {
    api,
    manipulate: async (uri: string): Promise<ProcessedAsset> => {
      const { ImageManipulator, SaveFormat } = await import("expo-image-manipulator")
      const { Image } = await import("react-native")
      const { getInfoAsync } = await import("expo-file-system/legacy")

      // Read the source dimensions so we only ever scale down, never up.
      const source = await new Promise<{ width: number; height: number }>((resolve, reject) =>
        Image.getSize(uri, (width, height) => resolve({ width, height }), reject),
      )
      const context = ImageManipulator.manipulate(uri)
      if (Math.max(source.width, source.height) > maxLongEdge) {
        context.resize(
          source.width >= source.height ? { width: maxLongEdge } : { height: maxLongEdge },
        )
      }
      const rendered = await context.renderAsync()
      // The JPEG re-encode is the EXIF/GPS strip — see module docstring.
      const result = await rendered.saveAsync({ format: SaveFormat.JPEG, compress: 0.8 })
      const info = await getInfoAsync(result.uri)
      return {
        uri: result.uri,
        width: result.width,
        height: result.height,
        byteLength: info.exists ? (info.size ?? 0) : 0,
      }
    },
    putFile: async (url: string, fileUri: string, contentType: string): Promise<number> => {
      const { uploadAsync, FileSystemUploadType } = await import("expo-file-system/legacy")
      const result = await uploadAsync(url, fileUri, {
        httpMethod: "PUT",
        headers: { "Content-Type": contentType },
        uploadType: FileSystemUploadType.BINARY_CONTENT,
      })
      return result.status
    },
  }
}
