/**
 * Client-side photo pre-processing for event-gallery uploads (GH-145 spec §3).
 *
 * Every picked file is downscaled to a max long edge and re-encoded as JPEG on
 * a canvas before upload. The canvas re-encode has a load-bearing side effect:
 * it drops ALL metadata, including embedded GPS coordinates — photos of minors
 * must never upload with a campsite's exact location baked in. Never bypass
 * this step to upload the original file bytes.
 */

export const MAX_LONG_EDGE = 2048
const JPEG_QUALITY = 0.8

export interface ProcessedPhoto {
  blob: Blob
  width: number
  height: number
  contentType: "image/jpeg"
}

/** The dimensions after scaling the long edge down to `maxEdge` (never up). */
export function fitWithin(
  width: number,
  height: number,
  maxEdge: number = MAX_LONG_EDGE,
): { width: number; height: number } {
  const longEdge = Math.max(width, height)
  if (longEdge <= maxEdge) return { width, height }
  const scale = maxEdge / longEdge
  return { width: Math.round(width * scale), height: Math.round(height * scale) }
}

export function isSupportedImage(file: File): boolean {
  // HEIC intentionally absent: browsers can't decode it onto a canvas, so it
  // can't go through the EXIF-stripping re-encode. Mobile handles HEIC natively.
  return ["image/jpeg", "image/png", "image/webp"].includes(file.type)
}

/** Downscale + strip metadata. Rejects if the file can't be decoded as an image. */
export async function processPhoto(file: File): Promise<ProcessedPhoto> {
  const bitmap = await createImageBitmap(file)
  try {
    const { width, height } = fitWithin(bitmap.width, bitmap.height)
    const canvas = document.createElement("canvas")
    canvas.width = width
    canvas.height = height
    const ctx = canvas.getContext("2d")
    if (!ctx) throw new Error("Canvas 2D context unavailable")
    ctx.drawImage(bitmap, 0, 0, width, height)

    const blob = await new Promise<Blob>((resolve, reject) => {
      canvas.toBlob(
        (b) => (b ? resolve(b) : reject(new Error("JPEG encode failed"))),
        "image/jpeg",
        JPEG_QUALITY,
      )
    })
    return { blob, width, height, contentType: "image/jpeg" }
  } finally {
    bitmap.close()
  }
}
