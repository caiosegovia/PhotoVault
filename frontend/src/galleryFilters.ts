export type GalleryFilter = {
  media: string;
  year: string;
  month: string;
  extension: string;
  deviceType: string;
  device: string;
  camera: string;
  size: "all" | "large" | "small";
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
  qualityScore: number;
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

  return items.filter((item) => {
    const sizeBytes = Number(item.sizeBytes || 0);
    if (media !== "all" && normalizeMedia(item.mediaType) !== media) return false;
    if (filter.year !== "all" && itemYear(item) !== filter.year) return false;
    if (filter.month !== "all" && itemMonth(item) !== filter.month) return false;
    if (extension !== "all" && normalizeExtension(item.extension) !== extension) return false;
    if (deviceType !== "all" && normalizeFacet(item.deviceType) !== deviceType) return false;
    if (device !== "all" && normalizeFacet(item.deviceName || item.deviceType) !== device) return false;
    if (camera !== "all" && normalizeFacet(`${item.cameraMake} ${item.cameraModel}`.trim()) !== camera) return false;
    if (filter.size === "large" && sizeBytes < 50 * 1024 * 1024) return false;
    if (filter.size === "small" && sizeBytes > 10 * 1024 * 1024) return false;
    if (filter.problem === "missing-thumb" && !hasMissingPreview(item)) return false;
    if (filter.problem === "without-date" && itemYear(item) !== "sem data") return false;
    if (filter.problem === "video" && !isVideo(item)) return false;
    if (filter.problem === "raw" && !isRaw(item)) return false;
    if (
      query &&
      !`${item.name} ${item.path} ${item.extension} ${item.date} ${item.deviceName} ${item.deviceType} ${item.cameraMake} ${item.cameraModel}`
        .toLowerCase()
        .includes(query)
    ) return false;
    return true;
  });
}
