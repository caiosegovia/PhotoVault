import { expect, test, type Page } from "@playwright/test";

type Item = {
  id: number;
  assetId: number;
  name: string;
  path: string;
  mediaType: string;
  extension: string;
  sizeBytes: number;
  date: string;
  deviceName: string;
  deviceType: string;
  cameraMake: string;
  cameraModel: string;
};

const baseItems: Item[] = [
  {
    id: 1,
    assetId: 101,
    name: "CANON_2026_06.JPG",
    path: "E:/Galeria/2026/06/CANON_2026_06.JPG",
    mediaType: "photo",
    extension: ".jpg",
    sizeBytes: 8 * 1024 * 1024,
    date: "2026-06-12",
    deviceName: "Canon EOS R6",
    deviceType: "camera",
    cameraMake: "Canon",
    cameraModel: "EOS R6",
  },
  {
    id: 2,
    assetId: 102,
    name: "DJI_2026_06.DNG",
    path: "E:/Galeria/2026/06/DJI_2026_06.DNG",
    mediaType: "photo",
    extension: ".dng",
    sizeBytes: 23 * 1024 * 1024,
    date: "2026-06-14",
    deviceName: "DJI FC7303",
    deviceType: "drone",
    cameraMake: "DJI",
    cameraModel: "FC7303",
  },
  {
    id: 3,
    assetId: 103,
    name: "SAMSUNG_2025_12.JPG",
    path: "E:/Galeria/2025/12/SAMSUNG_2025_12.JPG",
    mediaType: "photo",
    extension: ".jpg",
    sizeBytes: 5 * 1024 * 1024,
    date: "2025-12-24",
    deviceName: "Samsung SM-G781B",
    deviceType: "phone",
    cameraMake: "Samsung",
    cameraModel: "SM-G781B",
  },
  {
    id: 4,
    assetId: 104,
    name: "DRONE_2025_12.MP4",
    path: "E:/Galeria/2025/12/DRONE_2025_12.MP4",
    mediaType: "video",
    extension: ".mp4",
    sizeBytes: 120 * 1024 * 1024,
    date: "2025-12-19",
    deviceName: "DJI FC7303",
    deviceType: "drone",
    cameraMake: "DJI",
    cameraModel: "FC7303",
  },
  {
    id: 5,
    assetId: 105,
    name: "WHATSAPP_2025_11.JPG",
    path: "E:/Galeria/2025/11/WHATSAPP_2025_11.JPG",
    mediaType: "photo",
    extension: ".jpg",
    sizeBytes: 900 * 1024,
    date: "2025-11-02",
    deviceName: "WhatsApp",
    deviceType: "app",
    cameraMake: "",
    cameraModel: "",
  },
];

function normalizeExtension(value: string) {
  return value.toLowerCase().replace(/^\.+/, "");
}

function bucket(label: string, rows: Item[]) {
  const bytesRaw = rows.reduce((total, item) => total + item.sizeBytes, 0);
  return { label, count: rows.length, bytes: `${bytesRaw} B`, bytesRaw };
}

function buckets(items: Item[], getter: (item: Item) => string) {
  const grouped = new Map<string, Item[]>();
  for (const item of items) {
    const label = getter(item);
    grouped.set(label, [...(grouped.get(label) ?? []), item]);
  }
  return [...grouped.entries()]
    .map(([label, rows]) => bucket(label, rows))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));
}

function applyFilter(items: Item[], filter: Record<string, string> = {}) {
  return items.filter((item) => {
    if (filter.media && filter.media !== "all" && item.mediaType !== filter.media) return false;
    if (filter.year && filter.year !== "all" && item.date.slice(0, 4) !== filter.year) return false;
    if (filter.month && filter.month !== "all" && item.date.slice(0, 7) !== filter.month) return false;
    if (filter.extension && filter.extension !== "all" && normalizeExtension(item.extension) !== normalizeExtension(filter.extension)) return false;
    if (filter.deviceType && filter.deviceType !== "all" && item.deviceType !== filter.deviceType) return false;
    if (filter.device && filter.device !== "all" && item.deviceName.toLowerCase() !== filter.device.toLowerCase()) return false;
    if (filter.camera && filter.camera !== "all" && `${item.cameraMake} ${item.cameraModel}`.trim().toLowerCase() !== filter.camera.toLowerCase()) return false;
    if (filter.size === "large" && item.sizeBytes < 50 * 1024 * 1024) return false;
    if (filter.size === "medium" && (item.sizeBytes <= 10 * 1024 * 1024 || item.sizeBytes >= 50 * 1024 * 1024)) return false;
    if (filter.size === "small" && item.sizeBytes > 10 * 1024 * 1024) return false;
    return true;
  });
}

function galleryState(filter: Record<string, string> = {}) {
  const items = applyFilter(baseItems, filter);
  return {
    items: items.map((item) => ({
      ...item,
      thumbnail: "",
      previewStatus: "missing",
      size: `${item.sizeBytes} B`,
      resolution: "4000x3000",
      lensModel: "",
      software: "",
      qualityScore: 0,
      tags: "",
      noteCount: 0,
      latestNote: "",
    })),
    page: { limit: 240, offset: 0, count: items.length, hasMore: false },
    filteredTotal: items.length,
    total: baseItems.length,
    photos: baseItems.filter((item) => item.mediaType === "photo").length,
    videos: baseItems.filter((item) => item.mediaType === "video").length,
    withoutDate: 0,
    bytes: "126 MB",
    bytesTotal: baseItems.reduce((total, item) => total + item.sizeBytes, 0),
    photoBytes: "6 MB",
    photoBytesTotal: 6,
    videoBytes: "120 MB",
    videoBytesTotal: 120,
    firstDate: "2025-11-02",
    lastDate: "2026-06-14",
    yearCount: 2,
    monthCount: 3,
    extensionCount: 3,
    duplicateSavings: { count: 0, bytes: "0 B", bytesRaw: 0 },
    breakdowns: {
      media: buckets(baseItems, (item) => item.mediaType),
      years: buckets(baseItems, (item) => item.date.slice(0, 4)),
      months: buckets(baseItems, (item) => item.date.slice(0, 7)),
      extensions: buckets(baseItems, (item) => normalizeExtension(item.extension)),
      devices: buckets(baseItems, (item) => item.deviceName),
      deviceTypes: buckets(baseItems, (item) => item.deviceType),
      cameras: buckets(baseItems.filter((item) => item.cameraMake || item.cameraModel), (item) => `${item.cameraMake} ${item.cameraModel}`.trim()),
      lenses: [],
      sizes: [
        bucket("large", baseItems.filter((item) => item.sizeBytes >= 50 * 1024 * 1024)),
        bucket("medium", baseItems.filter((item) => item.sizeBytes > 10 * 1024 * 1024 && item.sizeBytes < 50 * 1024 * 1024)),
        bucket("small", baseItems.filter((item) => item.sizeBytes <= 10 * 1024 * 1024)),
      ].filter((item) => item.count),
      timeline: buckets(baseItems, (item) => item.date.slice(0, 7)),
    },
    capabilities: { ffmpegAvailable: true, exiftoolAvailable: true },
    processing: { exiftool: { total: 0 } },
  };
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("photovault.activeView", "gallery");
    window.localStorage.removeItem("photovault.galleryFilter");
  });
  await page.addInitScript(({ items }) => {
    const baseItems = items as Item[];
    function normalizeExtension(value: string) {
      return value.toLowerCase().replace(/^\.+/, "");
    }
    function bucket(label: string, rows: Item[]) {
      const bytesRaw = rows.reduce((total, item) => total + item.sizeBytes, 0);
      return { label, count: rows.length, bytes: `${bytesRaw} B`, bytesRaw };
    }
    function buckets(rows: Item[], getter: (item: Item) => string) {
      const grouped = new Map<string, Item[]>();
      for (const item of rows) {
        const label = getter(item);
        grouped.set(label, [...(grouped.get(label) ?? []), item]);
      }
      return [...grouped.entries()]
        .map(([label, groupedRows]) => bucket(label, groupedRows))
        .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));
    }
    function applyFilter(filter: Record<string, string> = {}) {
      return baseItems.filter((item) => {
        if (filter.media && filter.media !== "all" && item.mediaType !== filter.media) return false;
        if (filter.year && filter.year !== "all" && item.date.slice(0, 4) !== filter.year) return false;
        if (filter.month && filter.month !== "all" && item.date.slice(0, 7) !== filter.month) return false;
        if (filter.extension && filter.extension !== "all" && normalizeExtension(item.extension) !== normalizeExtension(filter.extension)) return false;
        if (filter.deviceType && filter.deviceType !== "all" && item.deviceType !== filter.deviceType) return false;
        if (filter.device && filter.device !== "all" && item.deviceName.toLowerCase() !== filter.device.toLowerCase()) return false;
        if (filter.camera && filter.camera !== "all" && `${item.cameraMake} ${item.cameraModel}`.trim().toLowerCase() !== filter.camera.toLowerCase()) return false;
        if (filter.size === "large" && item.sizeBytes < 50 * 1024 * 1024) return false;
        if (filter.size === "medium" && (item.sizeBytes <= 10 * 1024 * 1024 || item.sizeBytes >= 50 * 1024 * 1024)) return false;
        if (filter.size === "small" && item.sizeBytes > 10 * 1024 * 1024) return false;
        return true;
      });
    }
    function gallery(filter: Record<string, string> = {}) {
      const filtered = applyFilter(filter);
      return {
        items: filtered.map((item) => ({
          ...item,
          thumbnail: "",
          previewStatus: "missing",
          size: `${item.sizeBytes} B`,
          resolution: "4000x3000",
          lensModel: "",
          software: "",
          qualityScore: 0,
          tags: "",
          noteCount: 0,
          latestNote: "",
        })),
        page: { limit: 240, offset: 0, count: filtered.length, hasMore: false },
        filteredTotal: filtered.length,
        total: baseItems.length,
        photos: baseItems.filter((item) => item.mediaType === "photo").length,
        videos: baseItems.filter((item) => item.mediaType === "video").length,
        withoutDate: 0,
        bytes: "126 MB",
        bytesTotal: baseItems.reduce((total, item) => total + item.sizeBytes, 0),
        photoBytes: "6 MB",
        photoBytesTotal: 6,
        videoBytes: "120 MB",
        videoBytesTotal: 120,
        firstDate: "2025-11-02",
        lastDate: "2026-06-14",
        yearCount: 2,
        monthCount: 3,
        extensionCount: 3,
        duplicateSavings: { count: 0, bytes: "0 B", bytesRaw: 0 },
        breakdowns: {
          media: buckets(baseItems, (item) => item.mediaType),
          years: buckets(baseItems, (item) => item.date.slice(0, 4)),
          months: buckets(baseItems, (item) => item.date.slice(0, 7)),
          extensions: buckets(baseItems, (item) => normalizeExtension(item.extension)),
          devices: buckets(baseItems, (item) => item.deviceName),
          deviceTypes: buckets(baseItems, (item) => item.deviceType),
          cameras: buckets(baseItems.filter((item) => item.cameraMake || item.cameraModel), (item) => `${item.cameraMake} ${item.cameraModel}`.trim()),
          lenses: [],
          sizes: [
            bucket("large", baseItems.filter((item) => item.sizeBytes >= 50 * 1024 * 1024)),
            bucket("medium", baseItems.filter((item) => item.sizeBytes > 10 * 1024 * 1024 && item.sizeBytes < 50 * 1024 * 1024)),
            bucket("small", baseItems.filter((item) => item.sizeBytes <= 10 * 1024 * 1024)),
          ].filter((item) => item.count),
          timeline: buckets(baseItems, (item) => item.date.slice(0, 7)),
        },
        capabilities: { ffmpegAvailable: true, exiftoolAvailable: true },
        processing: { exiftool: { total: 0 } },
      };
    }
    // @ts-expect-error Tauri internals are mocked for browser e2e.
    window.__TAURI_INTERNALS__ = {
      invoke: async (cmd: string, args: { command?: string; payload?: { filter?: Record<string, string> } }) => {
        if (cmd === "progress_snapshot_native") {
          return { progress: { stage: "idle", status: "idle", message: "Sem processo.", current: 0, total: 0, path: "" }, logPath: "" };
        }
        if (cmd !== "bridge") return {};
        if (args.command === "state") {
          return {
            vault: { id: 1, name: "Galeria PhotoVault", path: "E:/Galeria", pattern: "{year}/{month:02d}", createdAt: "2026-01-01" },
            imports: [],
            files: [],
            importInsights: { reasonGroups: [], mediaGroups: [], statusGroups: [] },
            gallery: gallery(),
            disk: { total: 100, used: 10, free: 90, pending: 0 },
            progress: { stage: "idle", status: "idle", message: "Sem processo.", current: 0, total: 0, path: "" },
            diagnostics: { status: "ok", summary: "ok", requiredMissing: 0, optionalMissing: 0, tools: [], paths: [] },
            health: { total: 5, withoutDate: 0, largeVideos: 1, missingPath: 0, metadataPending: 0, openImports: 0, processing: {}, resumableImports: [], jobs: {}, insights: [] },
            logPath: "",
          };
        }
        if (args.command === "gallery") return gallery(args.payload?.filter ?? {});
        if (args.command === "catalog") return { tags: [], notes: [], related: [], history: [] };
        return {};
      },
      transformCallback: () => 1,
      unregisterCallback: () => undefined,
    };
  }, { items: baseItems });
});

function row(page: Page, name: string) {
  return page.locator(".media-row", { hasText: name });
}

function option(page: Page, label: string | RegExp) {
  return page.locator(".header-filter-popover button").filter({ hasText: label }).first();
}

test("gallery header filters update list, counters and clear state", async ({ page }) => {
  await page.goto("/");
  await expect(row(page, "CANON_2026_06.JPG")).toBeVisible();
  await expect(page.getByText("5 de 5 filtrados")).toBeVisible();

  await page.getByRole("button", { name: /Tipo\s+Todos/ }).click();
  await option(page, "Videos").click();
  await expect(row(page, "DRONE_2025_12.MP4")).toBeVisible();
  await expect(row(page, "CANON_2026_06.JPG")).toHaveCount(0);
  await expect(page.getByText("1 de 1 itens")).toBeVisible();

  await page.getByRole("button", { name: /Classe\s+Todas/ }).click();
  await option(page, "Drone").click();
  await expect(row(page, "DRONE_2025_12.MP4")).toBeVisible();
  await expect(page.getByText("Limpar (2)")).toBeVisible();

  await page.locator(".clear-header-filters").click();
  await expect(row(page, "CANON_2026_06.JPG")).toBeVisible();
  await expect(row(page, "WHATSAPP_2025_11.JPG")).toBeVisible();
  await expect(page.getByText("5 de 5 filtrados")).toBeVisible();
});

test("month, extension, device and size filters work from the visible menus", async ({ page }) => {
  await page.goto("/");

  await page.getByRole("button", { name: /Mes\s+Todos/ }).click();
  await option(page, "2026-06").click();
  await expect(row(page, "CANON_2026_06.JPG")).toBeVisible();
  await expect(row(page, "DJI_2026_06.DNG")).toBeVisible();
  await expect(row(page, "SAMSUNG_2025_12.JPG")).toHaveCount(0);

  await page.getByRole("button", { name: /Extensao\s+Todas/ }).click();
  await option(page, /\.dng/i).click();
  await expect(row(page, "DJI_2026_06.DNG")).toBeVisible();
  await expect(row(page, "CANON_2026_06.JPG")).toHaveCount(0);

  await page.locator(".clear-header-filters").click();
  await page.getByRole("button", { name: /Dispositivo\s+Todos/ }).click();
  await option(page, "Samsung SM-G781B").click();
  await expect(row(page, "SAMSUNG_2025_12.JPG")).toBeVisible();
  await expect(row(page, "WHATSAPP_2025_11.JPG")).toHaveCount(0);

  await page.locator(".clear-header-filters").click();
  await page.getByRole("button", { name: /Tamanho\s+Todos/ }).click();
  await option(page, "Grandes").click();
  await expect(row(page, "DRONE_2025_12.MP4")).toBeVisible();
  await expect(row(page, "CANON_2026_06.JPG")).toHaveCount(0);
});
