import {
  filterGalleryItems,
  galleryFilterKey,
  hasMissingPreview,
  isRaw,
  isVideo,
  mergeGalleryFilter,
  normalizeCameraName,
  normalizeGalleryFilter,
  type GalleryFilter,
  type GalleryItem,
} from "../src/galleryFilters.js";

function assertEqual<T>(actual: T, expected: T) {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(`Expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  }
}

const baseFilter: GalleryFilter = {
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

function item(partial: Partial<GalleryItem>): GalleryItem {
  return {
    id: partial.id ?? 1,
    assetId: partial.assetId ?? 1,
    name: partial.name ?? "IMG_0001.JPG",
    path: partial.path ?? "E:/Galeria/IMG_0001.JPG",
    thumbnail: partial.thumbnail ?? "thumb.jpg",
    previewStatus: partial.previewStatus ?? "ready",
    mediaType: partial.mediaType ?? "photo",
    extension: partial.extension ?? ".jpg",
    size: partial.size ?? "1 MB",
    sizeBytes: partial.sizeBytes ?? 1024 * 1024,
    date: partial.date ?? "2026-06-12",
    resolution: partial.resolution ?? "4000x3000",
    deviceName: partial.deviceName ?? "Canon EOS R6",
    deviceType: partial.deviceType ?? "camera",
    cameraMake: partial.cameraMake ?? "Canon",
    cameraModel: partial.cameraModel ?? "EOS R6",
    lensModel: partial.lensModel ?? "RF 24-70mm",
    qualityScore: partial.qualityScore ?? 0,
  };
}

const items = [
  item({ id: 1, extension: ".JPG", mediaType: "photo", date: "2026-06-12", thumbnail: "", deviceName: "Canon EOS R6", deviceType: "camera", cameraMake: "Canon", cameraModel: "EOS R6" }),
  item({ id: 2, extension: "dng", mediaType: "photo", date: "sem data", sizeBytes: 60 * 1024 * 1024, deviceName: "DJI FC7303", deviceType: "drone", cameraMake: "DJI", cameraModel: "FC7303" }),
  item({ id: 3, extension: ".MOV", mediaType: "other", date: "2024-12-01", sizeBytes: 5 * 1024 * 1024, deviceName: "Apple iPhone 14 Pro", deviceType: "phone", cameraMake: "Apple", cameraModel: "iPhone 14 Pro" }),
  item({ id: 4, extension: ".mp4", mediaType: "video", date: "2026-05-02", previewStatus: "placeholder", deviceName: "DJI/Drone", deviceType: "drone", cameraMake: "DJI", cameraModel: "Mini 4 Pro" }),
];

assertEqual(filterGalleryItems(items, { ...baseFilter, extension: "jpg" }).map((value) => value.id), [1]);
assertEqual(filterGalleryItems(items, { ...baseFilter, extension: ".DNG" }).map((value) => value.id), [2]);
assertEqual(filterGalleryItems(items, { ...baseFilter, problem: "raw" }).map((value) => value.id), [2]);
assertEqual(filterGalleryItems(items, { ...baseFilter, problem: "video" }).map((value) => value.id), [3, 4]);
assertEqual(filterGalleryItems(items, { ...baseFilter, problem: "missing-thumb" }).map((value) => value.id), [1, 4]);
assertEqual(filterGalleryItems(items, { ...baseFilter, problem: "without-date" }).map((value) => value.id), [2]);
assertEqual(filterGalleryItems(items, { ...baseFilter, year: "2026", month: "2026-06" }).map((value) => value.id), [1]);
assertEqual(filterGalleryItems(items, { ...baseFilter, deviceType: "drone" }).map((value) => value.id), [2, 4]);
assertEqual(filterGalleryItems(items, { ...baseFilter, deviceType: "phone" }).map((value) => value.id), [3]);
assertEqual(filterGalleryItems(items, { ...baseFilter, device: "DJI FC7303" }).map((value) => value.id), [2]);
assertEqual(filterGalleryItems(items, { ...baseFilter, device: "apple iphone 14 pro" }).map((value) => value.id), [3]);
assertEqual(filterGalleryItems(items, { ...baseFilter, camera: "DJI Mini 4 Pro" }).map((value) => value.id), [4]);
assertEqual(filterGalleryItems([item({ id: 5, deviceName: "DJI FC3582", deviceType: "drone", cameraMake: "", cameraModel: "FC3582" })], { ...baseFilter, camera: "DJI FC3582" }).map((value) => value.id), [5]);
assertEqual(filterGalleryItems(items, { ...baseFilter, lens: "RF 24-70mm" }).map((value) => value.id), [1, 2, 3, 4]);
assertEqual(filterGalleryItems(items, { ...baseFilter, device: "DJI/Drone", problem: "video" }).map((value) => value.id), [4]);
assertEqual(filterGalleryItems(items, { ...baseFilter, size: "large" }).map((value) => value.id), [2]);
assertEqual(filterGalleryItems(items, { ...baseFilter, size: "small" }).map((value) => value.id), [1, 3, 4]);
assertEqual(filterGalleryItems(items, { ...baseFilter, query: "galeria" }).map((value) => value.id), [1, 2, 3, 4]);
assertEqual(filterGalleryItems(items, { ...baseFilter, query: "drone" }).map((value) => value.id), [2, 4]);
assertEqual(filterGalleryItems(items, { ...baseFilter, query: "iphone" }).map((value) => value.id), [3]);
assertEqual(isRaw(items[1]), true);
assertEqual(isVideo(items[2]), true);
assertEqual(hasMissingPreview(items[0]), true);
assertEqual(normalizeCameraName("", "FC3582", "DJI FC3582"), "DJI FC3582");
assertEqual(normalizeCameraName("DJI", "DJI FC3582", ""), "DJI FC3582");

const mergedMonth = mergeGalleryFilter(baseFilter, { month: "2026-06" });
assertEqual(mergedMonth.year, "2026");
assertEqual(mergedMonth.month, "2026-06");

const combined = mergeGalleryFilter(mergedMonth, { extension: ".CR2" });
assertEqual(combined.year, "2026");
assertEqual(combined.month, "2026-06");
assertEqual(combined.extension, "cr2");

const combinedDevice = mergeGalleryFilter(combined, { device: "DJI FC7303" });
assertEqual(combinedDevice.month, "2026-06");
assertEqual(combinedDevice.extension, "cr2");
assertEqual(combinedDevice.device, "DJI FC7303");
assertEqual(combinedDevice.camera, "all");

const combinedCamera = mergeGalleryFilter(combinedDevice, { camera: "DJI FC7303" });
assertEqual(combinedCamera.device, "DJI FC7303");
assertEqual(combinedCamera.camera, "DJI FC7303");

const changedYear = mergeGalleryFilter(combinedCamera, { year: "2024" });
assertEqual(changedYear.year, "2024");
assertEqual(changedYear.month, "all");
assertEqual(changedYear.extension, "cr2");

const normalized = normalizeGalleryFilter({ extension: ".JPG", media: "PHOTO", query: " drone " });
assertEqual(normalized.extension, "jpg");
assertEqual(normalized.media, "photo");
assertEqual(galleryFilterKey(normalized).includes("drone"), true);
