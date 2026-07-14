import type { GalleryItem, GalleryPage } from "./galleryFilters";

export type ImportStatus = "ready" | "done" | "running" | "failed";
export type Decision = "import" | "skip" | "review";
export type View = "cockpit" | "gallery" | "import" | "reviews" | "logs";

export type ImportItem = {
  id: number;
  name: string;
  status: ImportStatus;
  rawStatus?: string;
  date: string;
  source: string;
  found: number;
  fresh: number;
  duplicates: number;
  errors: number;
  bytes: string;
  bytesNew: number;
  planId?: number;
};

export type Vault = { id?: number; name: string; path: string; pattern: string; createdAt?: string };
export type Disk = { total: number; used: number; free: number; pending: number };

export type Bucket = { label: string; count: number; bytes: string; bytesRaw: number };
export type TimelineBucket = Bucket & { photos?: number; videos?: number };
export type DuplicateSavings = { count: number; bytes: string; bytesRaw: number };
export type GalleryBreakdowns = {
  media: Bucket[];
  years: Bucket[];
  months: Bucket[];
  timeline?: TimelineBucket[];
  extensions: Bucket[];
  deviceTypes?: Bucket[];
  devices?: Bucket[];
  cameras?: Bucket[];
};

export type GalleryState = {
  items: GalleryItem[];
  page?: GalleryPage;
  total: number;
  filteredTotal?: number;
  photos: number;
  videos: number;
  withoutDate: number;
  bytes: string;
  bytesTotal: number;
  photoBytes: string;
  photoBytesTotal: number;
  videoBytes: string;
  videoBytesTotal: number;
  firstDate: string;
  lastDate: string;
  yearCount: number;
  monthCount: number;
  extensionCount: number;
  duplicateSavings: DuplicateSavings;
  breakdowns: GalleryBreakdowns;
  capabilities?: {
    ffmpegAvailable?: boolean;
    exiftoolAvailable?: boolean;
    exiftoolVersion?: string;
    exiftoolStatus?: { available?: boolean; path?: string; reason?: string };
  };
  processing?: { exiftool?: Record<string, number | string> };
  timings?: Record<string, number>;
  search?: { query: string; count: number; limit: number; offset?: number };
};

export type DecisionGroup = {
  reason: string;
  label: string;
  decision: Decision;
  mediaType: string;
  status: string;
  count: number;
  bytes: string;
  bytesRaw: number;
};

export type ImportInsights = { reasonGroups: DecisionGroup[]; mediaGroups: Bucket[]; statusGroups: Bucket[] };

export type ProgressInfo = {
  stage: string;
  message: string;
  current: number;
  total: number;
  path: string;
  status: string;
  metrics?: ProgressMetrics;
  updatedAt?: number;
  logPath?: string;
};

export type ProgressMetrics = {
  elapsedSeconds?: number;
  etaSeconds?: number;
  throughputMbps?: number;
  bytesImported?: number;
  filesCopied?: number;
  filesSkipped?: number;
  filesErrored?: number;
  lastFileMbps?: number;
  lastFileSeconds?: number;
  largestFile?: CopyFileMetric;
  slowestFile?: CopyFileMetric;
};

export type CopyFileMetric = { path: string; bytes: number; seconds: number; mbps: number };

export type DiagnosticItem = {
  label: string;
  available: boolean;
  required: boolean;
  path: string;
  version?: string;
  status: "ok" | "warning" | "error";
  detail?: string;
};

export type DiagnosticsState = {
  status: "ok" | "warning" | "error";
  summary: string;
  requiredMissing: number;
  optionalMissing: number;
  tools: DiagnosticItem[];
  paths: DiagnosticItem[];
  platform?: { system?: string; release?: string; machine?: string };
};

export type CatalogNote = { id: number; note_type: string; source: string; body: string; created_at: string };
export type AssetCatalog = { assetId: number; tags: string[]; notes: CatalogNote[] };
export type HealthInsight = { title: string; detail: string; action: string };
export type BackgroundJob = {
  id: number;
  kind: string;
  status: string;
  entity_type?: string;
  entity_id?: number;
  payload?: Record<string, unknown>;
  created_at?: string;
  started_at?: string;
  completed_at?: string;
  updated_at?: string;
  error?: string;
};

export type ResumableImport = {
  id: number;
  name: string;
  source_path: string;
  status: string;
  ingest_plan_id: number;
  operations: number;
  resumable: number;
  done: number;
  errors: number;
};

export type HealthState = {
  total: number;
  withoutDate: number;
  largeVideos: number;
  missingPath: number;
  metadataPending: number;
  openImports: number;
  processing?: Record<string, number>;
  resumableImports?: ResumableImport[];
  jobs?: Record<string, Record<string, number>>;
  recentJobs?: BackgroundJob[];
  insights?: HealthInsight[];
};

export type BackendState = {
  vault: Vault;
  imports: ImportItem[];
  importInsights: ImportInsights;
  gallery: GalleryState;
  disk: Disk;
  progress?: ProgressInfo;
  diagnostics?: DiagnosticsState;
  health?: HealthState;
  logPath?: string;
};

export type LogState = { logPath: string; lines: string[] };
