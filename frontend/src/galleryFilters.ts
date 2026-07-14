export type GalleryFilter = {
  media: string;
  year: string;
  month: string;
  extension: string;
  deviceType: string;
  device: string;
  camera: string;
  lens: string;
  size: "all" | "large" | "medium" | "small";
  query: string;
  problem: "all" | "missing-thumb" | "without-date" | "video" | "raw";
};

export type GalleryItem = {
  id: number;
  assetId: number;
  name: string;
  path: string;
  thumbnail: string;
  previewStatus: "ready" | "missing" | "placeholder";
  mediaType: string;
  extension: string;
  size: string;
  sizeBytes: number;
  date: string;
  resolution: string;
  deviceName: string;
  deviceType: string;
  cameraMake: string;
  cameraModel: string;
  lensModel?: string;
  software?: string;
  gpsLatitude?: string | number;
  gpsLongitude?: string | number;
  fileType?: string;
  mimeType?: string;
  codec?: string;
  bitrate?: string;
  frameRate?: string | number;
  iso?: string | number;
  aperture?: string | number;
  shutterSpeed?: string | number;
  focalLength?: string | number;
  metadataSource?: string;
  exiftoolVersion?: string;
  qualityScore: number;
  tags?: string;
  noteCount?: number;
  latestNote?: string;
};

export type GalleryPage = {
  limit: number;
  offset: number;
  count: number;
  hasMore: boolean;
};

export const DEFAULT_GALLERY_FILTER: GalleryFilter = {
  media: "all",
  year: "all",
  month: "all",
  extension: "all",
  deviceType: "all",
  device: "all",
  camera: "all",
  lens: "all",
  size: "all",
  query: "",
  problem: "all",
};

export const RAW_EXTENSIONS = new Set(["cr2", "cr3", "nef", "arw", "dng", "raf", "rw2", "orf"]);
const VIDEO_TYPES = new Set(["video", "movie"]);
const VIDEO_EXTENSIONS = new Set(["mp4", "mov", "m4v", "avi", "mkv", "3gp", "wmv", "mts", "m2ts"]);

function clean(value?: string) {
  return (value || "").trim();
}

export function normalizeExtension(value?: string) {
  return clean(value).toLowerCase().replace(/^\.+/, "");
}

export function normalizeMedia(value?: string) {
  return clean(value).toLowerCase();
}

export function normalizeFacet(value?: string) {
  return clean(value).toLowerCase();
}

function allIfEmpty(value?: string) {
  const cleaned = clean(value);
  return cleaned ? cleaned : "all";
}

export function normalizeGalleryFilter(filter: Partial<GalleryFilter>): GalleryFilter {
  const merged = { ...DEFAULT_GALLERY_FILTER, ...filter };
  return {
    media: normalizeMedia(merged.media) || "all",
    year: allIfEmpty(merged.year),
    month: allIfEmpty(merged.month),
    extension: normalizeExtension(merged.extension) || "all",
    deviceType: normalizeFacet(merged.deviceType) || "all",
    device: allIfEmpty(merged.device),
    camera: allIfEmpty(merged.camera),
    lens: allIfEmpty(merged.lens),
    size: (allIfEmpty(merged.size) as GalleryFilter["size"]),
    query: merged.query ?? "",
    problem: (allIfEmpty(merged.problem) as GalleryFilter["problem"]),
  };
}

export function mergeGalleryFilter(current: GalleryFilter, patch: Partial<GalleryFilter>): GalleryFilter {
  const next = normalizeGalleryFilter({ ...current, ...patch });
  if (patch.month !== undefined && next.month !== "all") {
    next.year = next.month.slice(0, 4);
  }
  if (patch.year !== undefined) {
    if (next.year === "all") {
      next.month = "all";
    } else if (patch.month === undefined && next.month !== "all" && next.month.slice(0, 4) !== next.year) {
      next.month = "all";
    }
  }
  return next;
}

export function galleryFilterKey(filter: GalleryFilter) {
  const normalized = normalizeGalleryFilter(filter);
  return [
    normalized.media,
    normalized.year,
    normalized.month,
    normalized.extension,
    normalized.deviceType,
    normalized.device,
    normalized.camera,
    normalized.lens,
    normalized.size,
    normalized.problem,
    normalized.query.trim(),
  ].join("\u001f");
}

export function normalizeCameraName(make?: string, model?: string, fallback?: string) {
  const rawMake = clean(make);
  let rawModel = clean(model);
  const upperMake = rawMake.toUpperCase();
  const upperModel = rawModel.toUpperCase();
  const isDji = upperMake.includes("DJI") || upperModel.startsWith("FC") || upperModel.startsWith("DJI ");
  if (upperModel.startsWith("DJI ")) rawModel = rawModel.slice(4).trim();
  if (isDji) return ["DJI", rawModel && rawModel.toUpperCase() !== "DJI" ? rawModel : ""].filter(Boolean).join(" ");
  return [rawMake, rawModel].filter(Boolean).join(" ") || clean(fallback) || "Desconhecido";
}

export function itemYear(item: GalleryItem) {
  const date = clean(item.date).toLowerCase();
  return date && date !== "sem data" ? date.slice(0, 4) : "sem data";
}

export function itemMonth(item: GalleryItem) {
  const date = clean(item.date).toLowerCase();
  return date && date !== "sem data" ? date.slice(0, 7) : "sem data";
}

export function isRaw(item: GalleryItem) {
  return RAW_EXTENSIONS.has(normalizeExtension(item.extension));
}

export function isVideo(item: GalleryItem) {
  return VIDEO_TYPES.has(normalizeMedia(item.mediaType)) || VIDEO_EXTENSIONS.has(normalizeExtension(item.extension));
}

export function hasMissingPreview(item: GalleryItem) {
  return item.previewStatus !== "ready" || !clean(item.thumbnail);
}

export function filterGalleryItems(items: GalleryItem[], filter: GalleryFilter) {
  const query = filter.query.trim().toLowerCase();
  const media = normalizeMedia(filter.media);
  const extension = normalizeExtension(filter.extension);
  const deviceType = normalizeFacet(filter.deviceType);
  const device = normalizeFacet(filter.device);
  const camera = normalizeFacet(filter.camera);
  const lens = normalizeFacet(filter.lens);

  return items.filter((item) => {
    const sizeBytes = Number(item.sizeBytes || 0);
    if (media !== "all" && normalizeMedia(item.mediaType) !== media) return false;
    if (filter.year !== "all" && itemYear(item) !== filter.year) return false;
    if (filter.month !== "all" && itemMonth(item) !== filter.month) return false;
    if (extension !== "all" && normalizeExtension(item.extension) !== extension) return false;
    if (deviceType !== "all" && normalizeFacet(item.deviceType) !== deviceType) return false;
    if (device !== "all" && normalizeFacet(item.deviceName || item.deviceType) !== device) return false;
    if (camera !== "all" && normalizeFacet(normalizeCameraName(item.cameraMake, item.cameraModel, item.deviceName)) !== camera) return false;
    if (lens !== "all" && normalizeFacet(item.lensModel) !== lens) return false;
    if (filter.size === "large" && sizeBytes < 50 * 1024 * 1024) return false;
    if (filter.size === "medium" && (sizeBytes <= 10 * 1024 * 1024 || sizeBytes >= 50 * 1024 * 1024)) return false;
    if (filter.size === "small" && sizeBytes > 10 * 1024 * 1024) return false;
    if (filter.problem === "missing-thumb" && !hasMissingPreview(item)) return false;
    if (filter.problem === "without-date" && itemYear(item) !== "sem data") return false;
    if (filter.problem === "video" && !isVideo(item)) return false;
    if (filter.problem === "raw" && !isRaw(item)) return false;
    if (
      query &&
      !`${item.name} ${item.path} ${item.extension} ${item.date} ${item.deviceName} ${item.deviceType} ${normalizeCameraName(item.cameraMake, item.cameraModel, item.deviceName)} ${item.lensModel ?? ""} ${item.software ?? ""} ${item.codec ?? ""} ${item.fileType ?? ""} ${item.tags ?? ""} ${item.latestNote ?? ""}`
        .toLowerCase()
        .includes(query)
    ) return false;
    return true;
  });
}
