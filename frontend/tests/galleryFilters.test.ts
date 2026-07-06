import { filterGalleryItems, hasMissingPreview, isRaw, isVideo, type GalleryFilter, type GalleryItem } from "../src/galleryFilters.js";

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
assertEqual(filterGalleryItems(items, { ...baseFilter, device: "DJI/Drone", problem: "video" }).map((value) => value.id), [4]);
assertEqual(filterGalleryItems(items, { ...baseFilter, size: "large" }).map((value) => value.id), [2]);
assertEqual(filterGalleryItems(items, { ...baseFilter, size: "small" }).map((value) => value.id), [1, 3, 4]);
assertEqual(filterGalleryItems(items, { ...baseFilter, query: "galeria" }).map((value) => value.id), [1, 2, 3, 4]);
assertEqual(filterGalleryItems(items, { ...baseFilter, query: "drone" }).map((value) => value.id), [2, 4]);
assertEqual(filterGalleryItems(items, { ...baseFilter, query: "iphone" }).map((value) => value.id), [3]);
assertEqual(isRaw(items[1]), true);
assertEqual(isVideo(items[2]), true);
assertEqual(hasMissingPreview(items[0]), true);
