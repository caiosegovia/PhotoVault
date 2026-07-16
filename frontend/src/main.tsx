import React from "react";
import ReactDOM from "react-dom/client";
import { convertFileSrc, invoke } from "@tauri-apps/api/core";
import {
  AlertTriangle,
  Archive,
  CalendarDays,
  Camera,
  CheckCircle2,
  Clock3,
  Database,
  Eye,
  FileWarning,
  Film,
  Filter,
  ExternalLink,
  FolderInput,
  FolderOpen,
  Gauge,
  HardDrive,
  ImageOff,
  Images,
  Layers3,
  ListChecks,
  Play,
  RotateCcw,
  Save,
  Search,
  Sparkles,
  Tag,
  Terminal,
  Trash2,
  Video,
} from "lucide-react";
import {
  DEFAULT_GALLERY_FILTER,
  galleryFilterKey,
  hasMissingPreview,
  isRaw,
  isVideo,
  itemYear,
  mergeGalleryFilter,
  normalizeGalleryFilter,
  normalizeCameraName,
  normalizeExtension,
  normalizeMedia,
  type GalleryFilter,
  type GalleryItem,
} from "./galleryFilters";
import type {
  AssetCatalog,
  BackgroundJob,
  BackendState,
  Bucket,
  Decision,
  DecisionGroup,
  DiagnosticItem,
  DiagnosticsState,
  Disk,
  DuplicateSavings,
  GalleryState,
  HealthState,
  ImportInsights,
  ImportItem,
  ImportStatus,
  LogState,
  ProgressInfo,
  ProgressMetrics,
  TimelineBucket,
  Vault,
  View,
} from "./contracts";
import "./styles.css";

const EMPTY_GALLERY: GalleryState = {
  items: [],
  page: { limit: 0, offset: 0, count: 0, hasMore: false },
  total: 0,
  photos: 0,
  videos: 0,
  withoutDate: 0,
  bytes: "0 B",
  bytesTotal: 0,
  photoBytes: "0 B",
  photoBytesTotal: 0,
  videoBytes: "0 B",
  videoBytesTotal: 0,
  firstDate: "",
  lastDate: "",
  yearCount: 0,
  monthCount: 0,
  extensionCount: 0,
  duplicateSavings: { count: 0, bytes: "0 B", bytesRaw: 0 },
  breakdowns: { media: [], years: [], months: [], extensions: [], deviceTypes: [], devices: [], cameras: [], lenses: [], sizes: [] },
  capabilities: { ffmpegAvailable: false, exiftoolAvailable: false },
};
const EMPTY_IMPORT_INSIGHTS: ImportInsights = { reasonGroups: [], mediaGroups: [], statusGroups: [] };
const EMPTY_DIAGNOSTICS: DiagnosticsState = {
  status: "warning",
  summary: "Diagnostico ainda nao carregado",
  requiredMissing: 0,
  optionalMissing: 0,
  tools: [],
  paths: [],
};
const EMPTY_HEALTH: HealthState = {
  total: 0,
  withoutDate: 0,
  largeVideos: 0,
  missingPath: 0,
  metadataPending: 0,
  openImports: 0,
  processing: {},
  resumableImports: [],
  jobs: {},
  insights: [],
};
const DEFAULT_FILTER = DEFAULT_GALLERY_FILTER;

function readStoredView(): View {
  try {
    const value = window.localStorage.getItem("photovault.activeView") as View | null;
    return value && ["cockpit", "gallery", "import", "reviews", "jobs", "logs"].includes(value) ? value : "cockpit";
  } catch {
    return "cockpit";
  }
}

function readStoredFilter(): GalleryFilter {
  try {
    const raw = window.localStorage.getItem("photovault.galleryFilter");
    return raw ? normalizeGalleryFilter(JSON.parse(raw)) : DEFAULT_FILTER;
  } catch {
    return DEFAULT_FILTER;
  }
}

const PATTERN_PRESETS = [
  { label: "Ano / mes", value: "{year}/{month:02d}" },
  { label: "Ano / mes / tipo", value: "{year}/{month:02d}/{media_type}" },
  { label: "Ano / camera", value: "{year}/{camera_make}" },
  { label: "Ano / extensao", value: "{year}/{extension}" },
  { label: "Mes compacto", value: "{year}-{month:02d}" },
];
const CAPACITY_RESERVE_BYTES = 1024 ** 3;
const GALLERY_PAGE_SIZE = 240;
type GallerySort = "date_desc" | "date_asc" | "size_desc" | "name_asc";

function formatNumber(value: number) {
  return value.toLocaleString("pt-BR");
}

function formatBytes(value: number) {
  if (!value) return "0 B";
  if (value < 1024) return `${value} B`;
  if (value < 1024 ** 2) return `${(value / 1024).toFixed(1)} KB`;
  if (value < 1024 ** 3) return `${(value / 1024 ** 2).toFixed(1)} MB`;
  return `${(value / 1024 ** 3).toFixed(2)} GB`;
}

function bucket(label: string, items: GalleryItem[]): Bucket {
  const bytesRaw = items.reduce((sum, item) => sum + Number(item.sizeBytes || 0), 0);
  return { label, count: items.length, bytes: formatBytes(bytesRaw), bytesRaw };
}

function sortBuckets(items: Bucket[]) {
  return [...items].sort((a, b) => b.count - a.count || a.label.localeCompare(b.label, "pt-BR"));
}

function bucketsBy(items: GalleryItem[], getter: (item: GalleryItem) => string, limit = 12) {
  const grouped = new Map<string, GalleryItem[]>();
  items.forEach((item) => {
    const label = getter(item) || "Desconhecido";
    grouped.set(label, [...(grouped.get(label) ?? []), item]);
  });
  return sortBuckets([...grouped.entries()].map(([label, rows]) => bucket(label, rows))).slice(0, limit);
}

function sizeBucketLabel(item: GalleryItem) {
  const size = Number(item.sizeBytes || 0);
  if (size >= 50 * 1024 * 1024) return "large";
  if (size <= 10 * 1024 * 1024) return "small";
  return "medium";
}

function statusLabel(status: ImportStatus) {
  return { ready: "Pronta", done: "Concluida", running: "Rodando", failed: "Falhou" }[status];
}

function decisionLabel(decision: Decision) {
  return { import: "Importar", skip: "Ignorar", review: "Revisar" }[decision];
}

function deviceTypeLabel(value?: string) {
  return {
    action_camera: "Acao",
    app: "App",
    camera: "Camera",
    drone: "Drone",
    phone: "Celular",
    unknown: "Desconhecido",
  }[value || ""] ?? (value || "Desconhecido");
}

function normalizeMediaLabel(value?: string) {
  return normalizeMedia(value || "media") || "media";
}

function mediaLabel(value?: string) {
  return { photo: "Fotos", video: "Videos", movie: "Videos" }[normalizeMediaLabel(value)] ?? (value || "Midia");
}

function sizeLabel(value?: string) {
  return { large: "Grandes", medium: "Medios", small: "Leves", all: "Todos" }[value || ""] ?? value ?? "";
}

function cleanMeta(value: unknown) {
  if (value === undefined || value === null || value === "") return "";
  return String(value);
}

function formatDecimal(value: unknown, digits = 1) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return cleanMeta(value);
  return numeric.toLocaleString("pt-BR", { maximumFractionDigits: digits });
}

function formatExposure(value: unknown) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric <= 0) return cleanMeta(value);
  if (numeric < 1) return `1/${Math.round(1 / numeric)}`;
  return `${formatDecimal(numeric, 2)} s`;
}

function formatBitrate(value: unknown) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric <= 0) return cleanMeta(value);
  if (numeric >= 1_000_000) return `${formatDecimal(numeric / 1_000_000, 1)} Mbps`;
  if (numeric >= 1_000) return `${formatDecimal(numeric / 1_000, 1)} Kbps`;
  return `${numeric} bps`;
}

function metadataBadge(item: GalleryItem | null) {
  if (!item) return "Aguardando selecao";
  return item.metadataSource === "ExifTool"
    ? `ExifTool ${item.exiftoolVersion ?? ""}`.trim()
    : "PhotoVault";
}

function facetTone(label?: string) {
  const value = normalizeMediaLabel(label);
  if (value === "photo") return "photo";
  if (value === "video" || value === "movie") return "video";
  if (value === "done" || value === "completed") return "done";
  if (value === "planned" || value === "ready") return "planned";
  if (value === "skipped" || value === "skip") return "skipped";
  if (value === "error" || value === "failed") return "failed";
  return "neutral";
}

function exiftoolStatusLabel(gallery: GalleryState) {
  const status = gallery.capabilities?.exiftoolStatus;
  if (gallery.capabilities?.exiftoolAvailable) {
    return `Disponivel ${gallery.capabilities?.exiftoolVersion ?? ""}`.trim();
  }
  if (status?.reason === "perl_missing") return "Script encontrado, falta Perl";
  if (status?.path) return "Encontrado, mas nao executavel";
  return "Ausente";
}

function exiftoolStatusDetail(gallery: GalleryState) {
  const status = gallery.capabilities?.exiftoolStatus;
  if (status?.path) return status.path;
  return "Instale exiftool.exe no PATH ou configure PHOTOVAULT_EXIFTOOL.";
}

function diagnosticsStatusLabel(diagnostics: DiagnosticsState) {
  if (diagnostics.status === "ok") {
    return diagnostics.optionalMissing ? `Pronto, ${diagnostics.optionalMissing} opcional ausente` : "Ambiente pronto";
  }
  return diagnostics.summary || "Revisar ambiente";
}

function diagnosticValue(item: DiagnosticItem) {
  if (!item.available) return item.required ? "Ausente" : "Opcional";
  return item.version ? `OK ${item.version}` : "OK";
}

async function callBridge<T>(command: string, payload: unknown = {}) {
  return invoke<T>("bridge", { command, payload });
}

async function pickNativeFolder(initial: string, title: string) {
  return invoke<string>("pick_folder_native", { initial, title });
}

async function openNativePath(path: string) {
  return invoke<void>("open_path_native", { path });
}

async function revealNativePath(path: string) {
  return invoke<void>("reveal_path_native", { path });
}

async function readProgressNative() {
  return invoke<{ progress: ProgressInfo; logPath: string }>("progress_snapshot_native");
}

function App() {
  const [activeView, setActiveView] = React.useState<View>(readStoredView);
  const [imports, setImports] = React.useState<ImportItem[]>([]);
  const [importInsights, setImportInsights] = React.useState<ImportInsights>(EMPTY_IMPORT_INSIGHTS);
  const [gallery, setGallery] = React.useState<GalleryState>(EMPTY_GALLERY);
  const [vault, setVault] = React.useState<Vault>({ name: "Galeria PhotoVault", path: "", pattern: "{year}/{month:02d}" });
  const [disk, setDisk] = React.useState<Disk>({ total: 0, used: 0, free: 0, pending: 0 });
  const [selectedImportId, setSelectedImportId] = React.useState<number | null>(null);
  const [selectedGalleryId, setSelectedGalleryId] = React.useState<number | null>(null);
  const [sourcePath, setSourcePath] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [galleryBusy, setGalleryBusy] = React.useState(false);
  const [thumbsBusy, setThumbsBusy] = React.useState(false);
  const [enrichBusy, setEnrichBusy] = React.useState(false);
  const [message, setMessage] = React.useState("Carregando estado real do PhotoVault...");
  const [progress, setProgress] = React.useState<ProgressInfo | null>(null);
  const [progressDismissed, setProgressDismissed] = React.useState(false);
  const [logPath, setLogPath] = React.useState("");
  const [logs, setLogs] = React.useState<LogState>({ logPath: "", lines: [] });
  const [diagnostics, setDiagnostics] = React.useState<DiagnosticsState>(EMPTY_DIAGNOSTICS);
  const [health, setHealth] = React.useState<HealthState>(EMPTY_HEALTH);
  const [catalog, setCatalog] = React.useState<AssetCatalog | null>(null);
  const [catalogBusy, setCatalogBusy] = React.useState(false);
  const [filter, setFilter] = React.useState<GalleryFilter>(readStoredFilter);
  const [gallerySort, setGallerySort] = React.useState<GallerySort>("date_desc");
  const progressTimerRef = React.useRef<number | null>(null);
  const galleryLoadingRef = React.useRef(false);
  const galleryRefreshQueuedRef = React.useRef<{ ensureThumbnails: boolean } | null>(null);
  const latestGalleryFilterRef = React.useRef(filter);
  const latestGallerySortRef = React.useRef(gallerySort);
  const galleryRequestSeqRef = React.useRef(0);
  const catalogRequestRef = React.useRef(0);

  const selectedImport = imports.find((item) => item.id === selectedImportId) ?? imports[0] ?? null;

  React.useEffect(() => {
    loadState();
    return () => stopProgressPolling();
  }, []);

  React.useEffect(() => {
    try {
      window.localStorage.setItem("photovault.activeView", activeView);
    } catch {
      // Preferences are best-effort only.
    }
  }, [activeView]);

  React.useEffect(() => {
    try {
      window.localStorage.setItem("photovault.galleryFilter", JSON.stringify(filter));
    } catch {
      // Preferences are best-effort only.
    }
    latestGalleryFilterRef.current = filter;
  }, [filter]);

  React.useEffect(() => {
    latestGallerySortRef.current = gallerySort;
  }, [gallerySort]);

  React.useEffect(() => {
    if (activeView === "logs") refreshLogs();
  }, [activeView]);

  React.useEffect(() => {
    if (activeView === "gallery" && gallery.total > 0 && gallery.items.length === 0) {
      refreshGallery(false);
    }
  }, [activeView, gallery.total, gallery.items.length]);

  React.useEffect(() => {
    if (activeView !== "gallery") return;
    const timer = window.setTimeout(() => refreshGallery(false), 260);
    return () => window.clearTimeout(timer);
  }, [
    activeView,
    filter.media,
    filter.year,
    filter.month,
    filter.extension,
    filter.deviceType,
    filter.device,
    filter.camera,
    filter.lens,
    filter.size,
    filter.problem,
    filter.query,
    gallerySort,
  ]);

  const filteredItems = React.useMemo(() => {
    return gallery.items;
  }, [gallery.items]);
  const selectedGalleryItem = filteredItems.find((item) => item.id === selectedGalleryId) ?? filteredItems[0] ?? null;

  React.useEffect(() => {
    if (!selectedGalleryItem?.assetId) {
      setCatalog(null);
      return;
    }
    const assetId = selectedGalleryItem.assetId;
    const timer = window.setTimeout(() => loadCatalog(assetId), 180);
    return () => window.clearTimeout(timer);
  }, [selectedGalleryItem?.assetId]);

  const counts = importInsights.reasonGroups.reduce(
    (acc, group) => {
      acc[group.decision] += group.count;
      return acc;
    },
    { import: 0, skip: 0, review: 0 } as Record<Decision, number>,
  );
  const importedTotal = imports.reduce((total, item) => total + item.fresh, 0);
  const duplicateTotal = imports.reduce((total, item) => total + item.duplicates, 0);
  const importedBytesTotal = imports.reduce((total, item) => total + item.bytesNew, 0);
  const errorTotal = imports.reduce((total, item) => total + item.errors, 0);
  const duplicateRate = selectedImport?.found ? Math.round((selectedImport.duplicates / selectedImport.found) * 100) : 0;
  const progressVisible = Boolean(progress && progress.status !== "idle" && !progressDismissed);
  const rawCount = gallery.items.filter(isRaw).length;
  const missingThumbCount = gallery.items.filter(hasMissingPreview).length;
  const largeVideoBytes = gallery.items
    .filter((item) => isVideo(item) && Number(item.sizeBytes || 0) > 50 * 1024 * 1024)
    .reduce((sum, item) => sum + Number(item.sizeBytes || 0), 0);
  const pendingPlanBytes = importInsights.statusGroups
    .filter((group) => ["planned", "running"].includes(group.label.toLowerCase()))
    .reduce((sum, group) => sum + group.bytesRaw, 0) || selectedImport?.bytesNew || 0;
  const capacityNeeded = pendingPlanBytes + CAPACITY_RESERVE_BYTES;
  const capacityShortfall = selectedImport?.planId && disk.free ? Math.max(capacityNeeded - disk.free, 0) : 0;
  const capacityWarning = capacityShortfall > 0
    ? `Livre: ${formatBytes(disk.free)}. Necessario para este plano: ${formatBytes(capacityNeeded)}. Faltam ${formatBytes(capacityShortfall)}.`
    : "";
  const canExecuteSelected = Boolean(selectedImport?.planId) && !capacityWarning;

  async function loadState(preferredImportId?: number) {
    try {
      const state = await callBridge<BackendState>("state");
      setVault(state.vault);
      setImports(state.imports);
      setImportInsights(state.importInsights ?? EMPTY_IMPORT_INSIGHTS);
      setGallery(state.gallery ?? EMPTY_GALLERY);
      setDisk(state.disk);
      setProgress(state.progress ?? null);
      setDiagnostics(state.diagnostics ?? EMPTY_DIAGNOSTICS);
      setHealth(state.health ?? EMPTY_HEALTH);
      if (state.progress?.status === "running") setProgressDismissed(false);
      setLogPath(state.logPath ?? state.progress?.logPath ?? "");
      setSelectedImportId(preferredImportId ?? selectedImportId ?? state.imports[0]?.id ?? null);
      setSelectedGalleryId((current) => current ?? state.gallery?.items[0]?.id ?? null);
      setMessage(state.imports.length ? "Estado carregado do banco real." : "Configure o vault e crie a primeira importacao.");
    } catch (error) {
      setMessage(`Erro ao carregar backend: ${String(error)}`);
    }
  }

  async function refreshGallery(ensureThumbnails = false) {
    if (galleryLoadingRef.current) {
      galleryRefreshQueuedRef.current = { ensureThumbnails: galleryRefreshQueuedRef.current?.ensureThumbnails || ensureThumbnails };
      return;
    }
    const requestId = ++galleryRequestSeqRef.current;
    const filterSnapshot = latestGalleryFilterRef.current;
    const sortSnapshot = latestGallerySortRef.current;
    const filterSnapshotKey = galleryFilterKey(filterSnapshot);
    galleryLoadingRef.current = true;
    setGalleryBusy(true);
    setThumbsBusy(ensureThumbnails);
    try {
      const result = await callBridge<GalleryState>("gallery", {
        limit: GALLERY_PAGE_SIZE,
        offset: 0,
        filter: filterSnapshot,
        query: filterSnapshot.query.trim(),
        sort: sortSnapshot,
        ensureThumbnails,
      });
      const stillLatest = requestId === galleryRequestSeqRef.current
        && filterSnapshotKey === galleryFilterKey(latestGalleryFilterRef.current)
        && sortSnapshot === latestGallerySortRef.current;
      if (!stillLatest) {
        galleryRefreshQueuedRef.current = { ensureThumbnails: galleryRefreshQueuedRef.current?.ensureThumbnails || ensureThumbnails };
        return;
      }
      setGallery(result);
      setSelectedGalleryId((current) => result.items.some((item) => item.id === current) ? current : result.items[0]?.id ?? null);
      setMessage(ensureThumbnails ? "Previews atualizados." : "Galeria atualizada.");
    } catch (error) {
      setMessage(`Erro ao atualizar galeria: ${String(error)}`);
    } finally {
      setThumbsBusy(false);
      setGalleryBusy(false);
      galleryLoadingRef.current = false;
      const queued = galleryRefreshQueuedRef.current;
      galleryRefreshQueuedRef.current = null;
      if (queued) void refreshGallery(queued.ensureThumbnails);
    }
  }

  async function loadMoreGallery() {
    if (galleryLoadingRef.current) return;
    if (!gallery.page?.hasMore) return;
    const filterSnapshot = latestGalleryFilterRef.current;
    const sortSnapshot = latestGallerySortRef.current;
    galleryLoadingRef.current = true;
    setGalleryBusy(true);
    try {
      const result = await callBridge<GalleryState>("gallery", {
        limit: GALLERY_PAGE_SIZE,
        offset: gallery.items.length,
        filter: filterSnapshot,
        query: filterSnapshot.query.trim(),
        sort: sortSnapshot,
      });
      setGallery((current) => ({
        ...result,
        items: [...current.items, ...result.items],
      }));
      setSelectedGalleryId((current) => result.items.some((item) => item.id === current) ? current : result.items[0]?.id ?? null);
      setMessage(`Galeria carregou mais ${formatNumber(result.items.length)} item(ns).`);
    } catch (error) {
      setMessage(`Erro ao carregar mais itens: ${String(error)}`);
    } finally {
      setGalleryBusy(false);
      galleryLoadingRef.current = false;
    }
  }

  async function refreshLogs() {
    try {
      const result = await callBridge<LogState>("logs", { lines: 220 });
      setLogs(result);
      setLogPath(result.logPath || logPath);
    } catch (error) {
      setMessage(`Erro ao ler logs: ${String(error)}`);
    }
  }

  async function refreshDiagnostics() {
    try {
      const result = await callBridge<DiagnosticsState>("diagnostics");
      setDiagnostics(result);
      setMessage(result.status === "ok" ? "Diagnostico de ambiente atualizado." : result.summary);
    } catch (error) {
      setMessage(`Erro ao diagnosticar ambiente: ${String(error)}`);
    }
  }

  async function refreshHealth() {
    try {
      const result = await callBridge<HealthState>("health");
      setHealth(result);
      setMessage("Saude da galeria atualizada.");
    } catch (error) {
      setMessage(`Erro ao atualizar saude: ${String(error)}`);
    }
  }

  async function controlJob(jobId: number, action: "pause" | "resume" | "cancel") {
    try {
      const result = await callBridge<{ ok: boolean; health: HealthState }>("job_control", { jobId, action });
      setHealth(result.health ?? health);
      await refreshProgress();
      setMessage(action === "pause" ? "Job pausado." : action === "resume" ? "Job retomado." : "Job cancelado.");
    } catch (error) {
      setMessage(`Erro ao controlar job: ${String(error)}`);
    }
  }

  async function loadCatalog(assetId: number) {
    const requestId = ++catalogRequestRef.current;
    setCatalogBusy(true);
    try {
      const result = await callBridge<AssetCatalog>("catalog", { assetId });
      if (requestId === catalogRequestRef.current) setCatalog(result);
    } catch (error) {
      if (requestId === catalogRequestRef.current) setMessage(`Erro ao carregar catalogo do item: ${String(error)}`);
    } finally {
      if (requestId === catalogRequestRef.current) setCatalogBusy(false);
    }
  }

  async function saveTags(assetId: number, tags: string[]) {
    setCatalogBusy(true);
    try {
      const result = await callBridge<{ catalog: AssetCatalog }>("update_tags", { assetId, tags });
      setCatalog(result.catalog);
      setGallery((current) => ({
        ...current,
        items: current.items.map((item) => item.assetId === assetId ? { ...item, tags: result.catalog.tags.join(", ") } : item),
      }));
      setMessage("Tags salvas.");
    } catch (error) {
      setMessage(`Erro ao salvar tags: ${String(error)}`);
    } finally {
      setCatalogBusy(false);
    }
  }

  async function saveNote(assetId: number, body: string) {
    setCatalogBusy(true);
    try {
      const result = await callBridge<{ catalog: AssetCatalog }>("add_note", { assetId, body });
      setCatalog(result.catalog);
      setGallery((current) => ({
        ...current,
        items: current.items.map((item) => item.assetId === assetId ? { ...item, noteCount: result.catalog.notes.length, latestNote: result.catalog.notes[0]?.body ?? "" } : item),
      }));
      setMessage("Nota adicionada.");
    } catch (error) {
      setMessage(`Erro ao salvar nota: ${String(error)}`);
    } finally {
      setCatalogBusy(false);
    }
  }

  async function pickFolder(target: "vault" | "source") {
    try {
      const path = await pickNativeFolder(
        target === "vault" ? vault.path : sourcePath,
        target === "vault" ? "Selecione o vault da galeria" : "Selecione a origem da importacao",
      );
      if (!path) return;
      if (target === "vault") setVault((current) => ({ ...current, path }));
      else setSourcePath(path);
    } catch (error) {
      setMessage(`Erro ao selecionar pasta: ${String(error)}`);
    }
  }

  async function openPath(path?: string) {
    if (!path) return;
    try {
      await openNativePath(path);
    } catch (error) {
      setMessage(`Erro ao abrir caminho: ${String(error)}`);
    }
  }

  async function revealPath(path?: string) {
    if (!path) return;
    try {
      await revealNativePath(path);
    } catch (error) {
      setMessage(`Erro ao localizar caminho: ${String(error)}`);
    }
  }

  async function resetAll() {
    const confirmed = window.confirm("Resetar banco, historico e cache local do PhotoVault? A galeria fisica nao sera apagada.");
    if (!confirmed) return;
    setBusy(true);
    setMessage("Resetando ambiente local...");
    try {
      const state = await callBridge<BackendState>("reset_all", { confirmReset: true });
      setVault(state.vault);
      setImports(state.imports);
      setImportInsights(state.importInsights ?? EMPTY_IMPORT_INSIGHTS);
      setGallery(state.gallery ?? EMPTY_GALLERY);
      setDisk(state.disk);
      setSelectedImportId(null);
      setSelectedGalleryId(null);
      setMessage("Ambiente resetado. Configure o vault e comece uma importacao nova.");
    } catch (error) {
      setMessage(`Erro ao resetar ambiente: ${String(error)}`);
    } finally {
      setBusy(false);
    }
  }

  async function saveVault() {
    setBusy(true);
    setMessage("Salvando vault...");
    try {
      await callBridge("set_vault", { name: vault.name, path: vault.path, pattern: vault.pattern });
      await loadState();
      setMessage("Vault salvo.");
    } catch (error) {
      setMessage(`Erro ao salvar vault: ${String(error)}`);
    } finally {
      setBusy(false);
    }
  }

  async function analyzeImport() {
    if (!sourcePath.trim()) {
      setMessage("Informe a pasta de origem para importar.");
      return;
    }
    setBusy(true);
    setMessage("Analisando importacao. Para pastas grandes isso pode levar alguns minutos...");
    setActiveView("jobs");
    startProgressPolling();
    try {
      const result = await callBridge<{ importId: number }>("analyze_import", {
        sourcePath,
        vaultPath: vault.path,
        pattern: vault.pattern,
        mode: "copy",
      });
      await loadState(result.importId);
      setActiveView("reviews");
      setMessage("Importacao analisada. Revise decisoes antes de executar.");
    } catch (error) {
      setMessage(`Erro ao analisar importacao: ${String(error)}`);
    } finally {
      setBusy(false);
      stopProgressPolling();
      await refreshProgress();
    }
  }

  async function selectImport(item: ImportItem) {
    setSelectedImportId(item.id);
    setMessage(`Carregando resumo de ${item.name}...`);
    try {
      const result = await callBridge<ImportInsights>("import_insights", { importId: item.id });
      setImportInsights(result);
      setMessage("Resumo da importacao carregado.");
    } catch (error) {
      setMessage(`Erro ao carregar resumo: ${String(error)}`);
    }
  }

  async function persistGroupDecision(group: DecisionGroup, decision: Decision) {
    if (!selectedImport?.id) return;
    setBusy(true);
    setMessage(`Aplicando ${decisionLabel(decision).toLowerCase()} em ${group.label.toLowerCase()}...`);
    try {
      const result = await callBridge<{ importInsights: ImportInsights; updated: number }>("update_decision_group", {
        importId: selectedImport.id,
        reason: group.reason,
        decision,
      });
      setImportInsights(result.importInsights);
      setMessage(`${formatNumber(result.updated)} arquivos atualizados.`);
    } catch (error) {
      setMessage(`Erro ao atualizar grupo: ${String(error)}`);
    } finally {
      setBusy(false);
    }
  }

  async function bulkDecision(decision: Decision) {
    if (!selectedImport?.id) return;
    setBusy(true);
    setMessage(`Aplicando ${decisionLabel(decision).toLowerCase()} nos grupos...`);
    try {
      let latestInsights = importInsights;
      let updated = 0;
      const groups = decision === "skip"
        ? importInsights.reasonGroups.filter((group) => group.reason !== "new_asset")
        : importInsights.reasonGroups;
      if (!groups.length) {
        setMessage("Nenhum grupo elegivel para esta acao em massa.");
        return;
      }
      for (const group of groups) {
        const result = await callBridge<{ importInsights: ImportInsights; updated: number }>("update_decision_group", {
          importId: selectedImport.id,
          reason: group.reason,
          decision,
        });
        latestInsights = result.importInsights;
        updated += result.updated;
      }
      setImportInsights(latestInsights);
      setMessage(`${formatNumber(updated)} arquivos atualizados.${decision === "skip" ? " Arquivos novos foram preservados para importacao." : ""}`);
    } catch (error) {
      setMessage(`Erro ao atualizar grupos: ${String(error)}`);
    } finally {
      setBusy(false);
    }
  }

  async function executeSelected() {
    if (!selectedImport?.planId) {
      setMessage("Selecione uma importacao com plano analisado.");
      return;
    }
    if (capacityWarning) {
      setMessage(`Espaco insuficiente no destino. ${capacityWarning}`);
      return;
    }
    setBusy(true);
    setMessage("Executando importacao aprovada...");
    setActiveView("jobs");
    startProgressPolling();
    try {
      await callBridge("execute_import", { planId: selectedImport.planId, verifyMode: "size" });
      await loadState(selectedImport.id);
      setActiveView("gallery");
      setMessage("Importacao, metadados e previews processados.");
    } catch (error) {
      await loadState(selectedImport.id);
      setMessage(`Erro ao executar importacao: ${String(error)}`);
    } finally {
      setBusy(false);
      stopProgressPolling();
      await refreshProgress();
    }
  }

  async function enrichMetadata() {
    setEnrichBusy(true);
    setMessage("Enriquecendo metadados com ExifTool...");
    setActiveView("jobs");
    startProgressPolling();
    try {
      const state = await callBridge<BackendState>("enrich_metadata", { limit: 2000 });
      setVault(state.vault);
      setImports(state.imports);
      setImportInsights(state.importInsights ?? EMPTY_IMPORT_INSIGHTS);
      setGallery(state.gallery ?? EMPTY_GALLERY);
      setDisk(state.disk);
      setProgress(state.progress ?? null);
      setProgressDismissed(false);
      setLogPath(state.logPath ?? state.progress?.logPath ?? "");
      setMessage(state.gallery?.capabilities?.exiftoolAvailable ? "Metadados enriquecidos." : "ExifTool ausente. Instale para habilitar enriquecimento rico.");
    } catch (error) {
      setMessage(`Erro ao enriquecer metadados: ${String(error)}`);
    } finally {
      setEnrichBusy(false);
      stopProgressPolling();
      await refreshProgress();
    }
  }

  async function refreshProgress() {
    try {
      const result = await readProgressNative();
      setProgress(result.progress);
      setLogPath(result.logPath || result.progress.logPath || "");
      if (result.progress.status === "running") {
        setProgressDismissed(false);
        setMessage(result.progress.message);
      }
    } catch (error) {
      setMessage(`Erro ao ler progresso: ${String(error)}`);
    }
  }

  function startProgressPolling() {
    stopProgressPolling();
    setProgressDismissed(false);
    let ticks = 0;
    const poll = async () => {
      ticks += 1;
      await refreshProgress();
      if (ticks > 360) {
        stopProgressPolling();
        return;
      }
      if (progressTimerRef.current !== null) {
        progressTimerRef.current = window.setTimeout(poll, 2000);
      }
    };
    progressTimerRef.current = window.setTimeout(poll, 250);
  }

  function stopProgressPolling() {
    if (progressTimerRef.current !== null) {
      window.clearTimeout(progressTimerRef.current);
      progressTimerRef.current = null;
    }
  }

  function dismissProgress() {
    setProgressDismissed(true);
  }

  function patchFilter(next: Partial<GalleryFilter>) {
    setFilter((current) => {
      const merged = mergeGalleryFilter(current, next);
      latestGalleryFilterRef.current = merged;
      return merged;
    });
    setActiveView("gallery");
  }

  const nav = [
    { id: "cockpit" as View, label: "Cockpit", icon: Gauge },
    { id: "gallery" as View, label: "Galeria", icon: Images },
    { id: "import" as View, label: "Importar", icon: FolderInput },
    { id: "reviews" as View, label: "Revisoes", icon: ListChecks },
    { id: "jobs" as View, label: "Jobs", icon: Clock3 },
    { id: "logs" as View, label: "Logs", icon: Database },
  ];

  return (
    <main className="app-shell">
      <aside className="rail">
        <div className="brand">
          <div className="brand-mark">PV</div>
          <div>
            <strong>PhotoVault</strong>
            <span>Galeria permanente</span>
          </div>
        </div>
        <nav>
          {nav.map((item) => {
            const Icon = item.icon;
            return (
              <button key={item.id} className={activeView === item.id ? "active" : ""} onClick={() => setActiveView(item.id)}>
                <Icon size={17} /> {item.label}
              </button>
            );
          })}
        </nav>
        <div className="rail-section">
          <span>Vault ativo</span>
          <strong>{vault.name || "Galeria PhotoVault"}</strong>
          <span className="rail-path">{vault.path || "nao configurado"}</span>
        </div>
      </aside>

      <section className="workspace">
        <header className="topbar compact">
          <div>
            <p className="eyebrow"><Layers3 size={15} /> {activeView}</p>
            <h1>{headline(activeView, gallery, selectedImport, vault)}</h1>
            <p>{message}</p>
          </div>
        </header>

        {activeView === "cockpit" ? (
          <CockpitView
            gallery={gallery}
            vault={vault}
            disk={disk}
            imports={imports}
            selectedImport={selectedImport}
            duplicateTotal={duplicateTotal}
            importedTotal={importedTotal}
            errorTotal={errorTotal}
            importedBytesTotal={importedBytesTotal}
            rawCount={rawCount}
            missingThumbCount={missingThumbCount}
            largeVideoBytes={largeVideoBytes}
            diagnostics={diagnostics}
            health={health}
            enrichBusy={enrichBusy}
            onFilter={patchFilter}
            onView={setActiveView}
            onEnrich={enrichMetadata}
            onDiagnostics={refreshDiagnostics}
            onHealth={refreshHealth}
          />
        ) : null}

        {activeView === "gallery" ? (
          <GalleryView
            gallery={gallery}
            vault={vault}
            imports={imports}
            filter={filter}
            sort={gallerySort}
            items={filteredItems}
            selectedItem={selectedGalleryItem}
            catalog={catalog}
            catalogBusy={catalogBusy}
            galleryBusy={galleryBusy}
            thumbsBusy={thumbsBusy}
            enrichBusy={enrichBusy}
            onFilter={patchFilter}
            onSort={(sort) => {
              latestGallerySortRef.current = sort;
              setGallerySort(sort);
            }}
            onClear={() => {
              latestGalleryFilterRef.current = DEFAULT_FILTER;
              setFilter(DEFAULT_FILTER);
            }}
            onSelect={setSelectedGalleryId}
            onRefresh={() => refreshGallery(false)}
            onLoadMore={loadMoreGallery}
            onHydrate={() => refreshGallery(true)}
            onEnrich={enrichMetadata}
            onOpenPath={openPath}
            onRevealPath={revealPath}
            onSaveTags={saveTags}
            onSaveNote={saveNote}
          />
        ) : null}

        {activeView === "import" ? (
          <ImportView
            vault={vault}
            sourcePath={sourcePath}
            busy={busy}
            progress={progress}
            progressVisible={false}
            disk={disk}
            onVault={setVault}
            onSource={setSourcePath}
            onPickFolder={pickFolder}
            onOpenPath={openPath}
            onSave={saveVault}
            onAnalyze={analyzeImport}
            onExecute={executeSelected}
            onReset={resetAll}
            onDismissProgress={dismissProgress}
            canExecute={canExecuteSelected}
            capacityWarning={capacityWarning}
          />
        ) : null}

        {activeView === "reviews" ? (
          <ReviewsView
            imports={imports}
            selectedImport={selectedImport}
            importInsights={importInsights}
            counts={counts}
            busy={busy}
            duplicateRate={duplicateRate}
            onSelectImport={selectImport}
            onBulk={bulkDecision}
            onDecision={persistGroupDecision}
            onExecute={executeSelected}
            canExecute={canExecuteSelected}
            capacityWarning={capacityWarning}
          />
        ) : null}

        {activeView === "jobs" ? (
          <JobsView
            health={health}
            progress={progress}
            progressVisible={progressVisible}
            logPath={logPath}
            onRefresh={() => {
              void refreshProgress();
              void refreshHealth();
            }}
            onDismissProgress={dismissProgress}
            onViewLogs={() => setActiveView("logs")}
            onJobAction={controlJob}
          />
        ) : null}

        {activeView === "logs" ? <LogsView logs={logs} logPath={logPath} onRefresh={refreshLogs} /> : null}
      </section>
    </main>
  );
}

function headline(view: View, gallery: GalleryState, selectedImport: ImportItem | null, vault: Vault) {
  if (view === "gallery") return vault.name || `${formatNumber(gallery.total)} arquivos preservados`;
  if (view === "import") return "Nova importacao";
  if (view === "reviews") return selectedImport ? `Revisao de ${selectedImport.name}` : "Revisoes de importacao";
  if (view === "jobs") return "Jobs da galeria";
  if (view === "logs") return "Operacao e auditoria";
  return "Cockpit da galeria";
}

function CockpitView({
  gallery,
  vault,
  disk,
  imports,
  selectedImport,
  duplicateTotal,
  importedTotal,
  errorTotal,
  importedBytesTotal,
  rawCount,
  missingThumbCount,
  largeVideoBytes,
  diagnostics,
  health,
  enrichBusy,
  onFilter,
  onView,
  onEnrich,
  onDiagnostics,
  onHealth,
}: {
  gallery: GalleryState;
  vault: Vault;
  disk: Disk;
  imports: ImportItem[];
  selectedImport: ImportItem | null;
  duplicateTotal: number;
  importedTotal: number;
  errorTotal: number;
  importedBytesTotal: number;
  rawCount: number;
  missingThumbCount: number;
  largeVideoBytes: number;
  diagnostics: DiagnosticsState;
  health: HealthState;
  enrichBusy: boolean;
  onFilter: (filter: Partial<GalleryFilter>) => void;
  onView: (view: View) => void;
  onEnrich: () => void;
  onDiagnostics: () => void;
  onHealth: () => void;
}) {
  const duplicateSavings = gallery.duplicateSavings?.bytesRaw ? gallery.duplicateSavings : {
    count: duplicateTotal,
    bytes: "0 B",
    bytesRaw: 0,
  };
  const healthIssues = [
    errorTotal ? `${formatNumber(errorTotal)} erros` : "",
    health.metadataPending ? `${formatNumber(health.metadataPending)} metadados` : "",
    health.withoutDate ? `${formatNumber(health.withoutDate)} sem data` : "",
    diagnostics.requiredMissing ? `${formatNumber(diagnostics.requiredMissing)} dependencia` : "",
  ].filter(Boolean);
  const intelligenceGroups = [
    {
      title: "Qualidade do catalogo",
      detail: "Itens que atrapalham timeline, busca e revisao visual.",
      items: [
        { icon: ImageOff, title: "Sem preview", value: formatNumber(missingThumbCount), detail: "Gerar thumbs ou validar midias quebradas", action: "Filtrar", onClick: () => onFilter({ problem: "missing-thumb" }) },
        { icon: CalendarDays, title: "Sem data", value: formatNumber(gallery.withoutDate), detail: "Arquivos fora da timeline confiavel", action: "Ver", onClick: () => onFilter({ problem: "without-date" }) },
      ],
    },
    {
      title: "Armazenamento",
      detail: "Arquivos que mais pesam no vault e merecem curadoria.",
      items: [
        { icon: Sparkles, title: "RAW", value: formatNumber(rawCount), detail: "Originais pesados para revisao fina", action: "Abrir", onClick: () => onFilter({ problem: "raw" }) },
        { icon: Film, title: "Videos grandes", value: formatBytes(largeVideoBytes), detail: "Consumo relevante de espaco", action: "Revisar", onClick: () => onFilter({ problem: "video", size: "large" }) },
      ],
    },
    {
      title: "Origem e captura",
      detail: "Sinais para separar camera, celular, drone e apps.",
      items: [
        { icon: Camera, title: "Cameras", value: formatNumber(gallery.breakdowns.cameras?.length ?? 0), detail: "Modelos identificados por metadados", action: "Ver", onClick: () => onFilter({ problem: "all" }) },
        { icon: Gauge, title: "Dispositivos", value: formatNumber(gallery.breakdowns.devices?.length ?? 0), detail: "Classes e modelos detectados", action: "Abrir", onClick: () => onFilter({ problem: "all" }) },
      ],
    },
  ];

  return (
    <div className="view-stack">
      <GalleryHealthSection
        diagnostics={diagnostics}
        health={health}
        gallery={gallery}
        disk={disk}
        selectedImport={selectedImport}
        errors={errorTotal}
        issues={healthIssues}
        onFilter={onFilter}
        onView={onView}
        onHealth={onHealth}
      />

      <GalleryIdentity vault={vault} gallery={gallery} disk={disk} savings={duplicateSavings} />

      <section className="cockpit-grid">
        <div className="panel span-2">
          <SectionTitle eyebrow="Na galeria" title="Composicao do acervo permanente" />
          <GallerySummaryPanel
            gallery={gallery}
            imports={imports}
            duplicateSavings={duplicateSavings}
            importedBytesTotal={importedBytesTotal}
            onFilter={onFilter}
            onView={onView}
          />
        </div>

        <div className="panel span-2">
          <SectionTitle eyebrow="Inteligencia da galeria" title="Proximas melhores acoes" />
          <div className="insight-groups">
            {intelligenceGroups.map((group) => (
              <InsightGroup key={group.title} title={group.title} detail={group.detail} items={group.items} />
            ))}
          </div>
        </div>

        <div className="panel">
          <SectionTitle eyebrow="Distribuicao" title="Midia" />
          <MediaDistribution items={gallery.breakdowns.media} onPick={(label) => onFilter({ media: label })} />
        </div>

        <div className="panel span-3">
          <SectionTitle eyebrow="Linha do tempo" title="Quando o acervo foi produzido" />
          <GalleryTimeline items={gallery.breakdowns.timeline ?? gallery.breakdowns.months} onPick={(label) => onFilter({ month: label })} />
        </div>

        <div className="panel span-2">
          <SectionTitle eyebrow="Espaco" title="Peso por extensao" />
          <BarChart items={gallery.breakdowns.extensions} mode="bytes" onPick={(label) => onFilter({ extension: label.toLowerCase() })} />
        </div>

        <div className="panel">
          <SectionTitle eyebrow="Origem tecnica" title="Classes detectadas" />
          <FacetButtons items={gallery.breakdowns.deviceTypes ?? []} labelFor={deviceTypeLabel} onPick={(label) => onFilter({ deviceType: label, problem: "all" })} />
        </div>

        <div className="panel">
          <SectionTitle eyebrow="Dispositivo" title="Modelos detectados" />
          <DeviceBreakdown items={gallery.breakdowns.devices ?? []} onPick={(label) => onFilter({ device: label, problem: "all" })} />
        </div>

        <div className="panel">
          <SectionTitle eyebrow="Metadados" title="Enriquecimento" />
          <Signal
            label="ExifTool"
            value={exiftoolStatusLabel(gallery)}
            tone={gallery.capabilities?.exiftoolAvailable ? "good" : "bad"}
          />
          <p className="path-copy">{exiftoolStatusDetail(gallery)}</p>
          <Signal label="Cameras" value={formatNumber(gallery.breakdowns.cameras?.length ?? 0)} />
          <button className="primary full" onClick={onEnrich} disabled={enrichBusy || !gallery.total}>
            <Sparkles size={16} /> {enrichBusy ? "Enriquecendo..." : "Enriquecer"}
          </button>
        </div>

        <div className="panel span-2">
          <SectionTitle eyebrow="Importacoes recentes" title={`${formatNumber(imports.length)} ciclos registrados`} action="Revisoes" onAction={() => onView("reviews")} />
          <div className="import-row-list">
            {imports.slice(0, 5).map((item) => (
              <div className="import-row-card" key={item.id}>
                <span className={`status ${item.status}`}>{statusLabel(item.status)}</span>
                <strong>{item.name}</strong>
                <p>{formatNumber(item.found)} encontrados | {formatNumber(item.fresh)} novos | {formatNumber(item.duplicates)} duplicados | {item.bytes}</p>
              </div>
            ))}
            {!imports.length ? <EmptyState text="Nenhuma importacao registrada ainda." /> : null}
          </div>
        </div>

        <div className="panel span-2">
          <SectionTitle eyebrow="Ambiente" title={diagnosticsStatusLabel(diagnostics)} action="Atualizar" onAction={onDiagnostics} />
          <DiagnosticsPanel diagnostics={diagnostics} />
        </div>
      </section>
    </div>
  );
}

function formatDateShort(value?: string) {
  if (!value) return "-";
  const date = value.slice(0, 10);
  const [year, month, day] = date.split("-");
  return year && month && day ? `${day}/${month}/${year}` : date;
}

function GalleryHealthSection({
  diagnostics,
  health,
  gallery,
  disk,
  selectedImport,
  errors,
  issues,
  onFilter,
  onView,
  onHealth,
}: {
  diagnostics: DiagnosticsState;
  health: HealthState;
  gallery: GalleryState;
  disk: Disk;
  selectedImport: ImportItem | null;
  errors: number;
  issues: string[];
  onFilter: (filter: Partial<GalleryFilter>) => void;
  onView: (view: View) => void;
  onHealth: () => void;
}) {
  const freePct = disk.total ? Math.round((disk.free / disk.total) * 100) : 0;
  const hardIssues = [
    diagnostics.requiredMissing,
    errors,
    freePct > 0 && freePct < 10 ? 1 : 0,
    health.resumableImports?.length ?? 0,
  ].filter(Boolean).length;
  const warningIssues = [
    health.metadataPending,
    health.withoutDate,
    health.largeVideos,
    diagnostics.optionalMissing,
  ].filter(Boolean).length;
  const score = Math.max(0, 100 - hardIssues * 22 - warningIssues * 8);
  const tone = hardIssues ? "bad" : warningIssues || issues.length ? "warn" : "good";
  const summary = issues.length ? issues.slice(0, 3).join(" | ") : "Sem alertas principais";
  const jobCounts = Object.values(health.jobs ?? {}).reduce(
    (acc, group) => {
      acc.running += group.running ?? 0;
      acc.error += (group.error ?? 0) + (group.failed ?? 0);
      acc.done += group.done ?? 0;
      return acc;
    },
    { running: 0, error: 0, done: 0 },
  );
  const metadataPct = health.total ? Math.max(0, Math.round(((health.total - (health.metadataPending || 0)) / health.total) * 100)) : 100;
  const datedPct = health.total ? Math.max(0, Math.round(((health.total - (health.withoutDate || 0)) / health.total) * 100)) : 100;
  const jobHealthPct = jobCounts.running || jobCounts.error ? Math.max(0, 100 - jobCounts.error * 20) : 100;
  const scoreLabel = score >= 85 ? "Saudavel" : score >= 65 ? "Atencao" : "Critica";
  return (
    <section className={`gallery-health-section ${tone}`}>
      <div className="health-pill-bar">
        <div className={`health-score-pill ${tone}`}>
          <Gauge size={17} />
          <span>Saude</span>
          <strong>{score}</strong>
          <em>{scoreLabel}</em>
        </div>
        <Signal label="Espaco livre" value={`${formatBytes(disk.free)} (${freePct}%)`} tone={freePct > 15 ? "good" : "bad"} />
        <Signal label="Metadados" value={`${formatNumber(health.metadataPending || 0)} pend.`} tone={health.metadataPending ? "bad" : "good"} />
        <Signal label="Datas" value={`${formatNumber(health.withoutDate || 0)} sem data`} tone={health.withoutDate ? "bad" : "good"} />
        <Signal label="Dependencias" value={diagnostics.requiredMissing ? `${formatNumber(diagnostics.requiredMissing)} pend.` : "OK"} tone={diagnostics.requiredMissing ? "bad" : "good"} />
        <Signal label="Erros" value={formatNumber(errors)} tone={errors ? "bad" : "good"} />
      </div>
      <div className="health-overview-grid">
        <HealthGaugeCard label="Catalogo" value={`${formatNumber(gallery.total)} itens`} detail={summary} pct={score} tone={tone} />
        <HealthGaugeCard label="Metadados" value={`${metadataPct}% ok`} detail={`${formatNumber(health.metadataPending || 0)} pendentes`} pct={metadataPct} tone={health.metadataPending ? "warn" : "good"} />
        <HealthGaugeCard label="Timeline" value={`${datedPct}% datado`} detail={`${formatNumber(health.withoutDate || 0)} sem captura`} pct={datedPct} tone={health.withoutDate ? "warn" : "good"} />
        <HealthGaugeCard label="Jobs" value={`${formatNumber(jobCounts.running)} rodando`} detail={`${formatNumber(jobCounts.done)} concluidos | ${formatNumber(jobCounts.error)} erro(s)`} pct={jobHealthPct} tone={jobCounts.error ? "bad" : jobCounts.running ? "warn" : "good"} />
      </div>
      <div className="health-action-row">
        <button className="secondary" onClick={onHealth}><RotateCcw size={15} /> Atualizar saude</button>
        <button className="secondary" onClick={() => onFilter({ problem: "without-date" })}><CalendarDays size={15} /> Sem data</button>
        <button className="secondary" onClick={() => onFilter({ problem: "video", size: "large" })}><Film size={15} /> Videos grandes</button>
        <button className="secondary" onClick={() => onView("jobs")}><Clock3 size={15} /> Ver jobs</button>
      </div>
      {(health.insights ?? []).length ? (
        <div className="health-insight-strip">
          {(health.insights ?? []).slice(0, 2).map((item) => (
            <article key={item.title}>
              <strong>{item.title}</strong>
              <span>{item.detail}</span>
            </article>
          ))}
        </div>
      ) : null}
    </section>
  );
}

function HealthGaugeCard({ label, value, detail, pct, tone }: { label: string; value: string; detail: string; pct: number; tone: "good" | "warn" | "bad" }) {
  return (
    <article className={`health-gauge-card ${tone}`}>
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
        <em>{detail}</em>
      </div>
      <i><b style={{ width: `${Math.max(0, Math.min(pct, 100))}%` }} /></i>
    </article>
  );
}

function HealthStatusCard({ icon: Icon, label, value, detail, tone }: { icon: React.ElementType; label: string; value: string; detail: string; tone: "good" | "warn" | "bad" }) {
  return (
    <article className={`health-status-card ${tone}`}>
      <Icon size={17} />
      <span>{label}</span>
      <strong>{value}</strong>
      <em>{detail}</em>
    </article>
  );
}

function GallerySummaryPanel({
  gallery,
  imports,
  duplicateSavings,
  importedBytesTotal,
  onFilter,
  onView,
}: {
  gallery: GalleryState;
  imports: ImportItem[];
  duplicateSavings: DuplicateSavings;
  importedBytesTotal: number;
  onFilter: (filter: Partial<GalleryFilter>) => void;
  onView: (view: View) => void;
}) {
  return (
    <div className="gallery-summary-panel">
      <div className="summary-pill-grid">
        <SummaryPill icon={Camera} label="Fotos" value={formatNumber(gallery.photos)} detail={gallery.photoBytes || "0 B"} onClick={() => onFilter({ media: "photo" })} />
        <SummaryPill icon={Video} label="Videos" value={formatNumber(gallery.videos)} detail={gallery.videoBytes || "0 B"} onClick={() => onFilter({ media: "video" })} />
        <SummaryPill icon={CalendarDays} label="Periodo" value={dateRangeLabel(gallery)} detail={`${formatNumber(gallery.monthCount)} meses ativos`} />
        <SummaryPill icon={CheckCircle2} label="Duplicatas evitadas" value={formatNumber(duplicateSavings.count)} detail={duplicateSavings.bytes} />
        <SummaryPill icon={Database} label="Importado" value={formatBytes(importedBytesTotal)} detail={`${formatNumber(imports.length)} ciclos registrados`} onClick={() => onView("reviews")} />
      </div>
      <ArchiveOrganization gallery={gallery} />
    </div>
  );
}

function SummaryPill({ icon: Icon, label, value, detail, onClick }: { icon: React.ElementType; label: string; value: string; detail: string; onClick?: () => void }) {
  const content = (
    <>
      <Icon size={16} />
      <span>{label}</span>
      <strong>{value}</strong>
      <em>{detail}</em>
    </>
  );
  if (onClick) return <button className="summary-pill" onClick={onClick}>{content}</button>;
  return <div className="summary-pill">{content}</div>;
}

function ArchiveOrganization({ gallery }: { gallery: GalleryState }) {
  const topYear = [...gallery.breakdowns.years].sort((a, b) => b.bytesRaw - a.bytesRaw)[0];
  const topExtension = [...gallery.breakdowns.extensions].sort((a, b) => b.bytesRaw - a.bytesRaw)[0];
  const topDevice = [...(gallery.breakdowns.devices ?? [])].sort((a, b) => b.count - a.count)[0];
  const classes = gallery.breakdowns.deviceTypes?.length ?? 0;
  return (
    <div className="archive-organization">
      <div className="org-heading">
        <Layers3 size={16} />
        <div>
          <strong>Organizacao do acervo</strong>
          <span>{formatNumber(gallery.yearCount)} anos | {formatNumber(gallery.monthCount)} meses | {formatNumber(gallery.extensionCount)} formatos | {formatNumber(gallery.breakdowns.devices?.length ?? 0)} dispositivos | {formatNumber(classes)} classes</span>
        </div>
      </div>
      <div className="org-highlights">
        <Signal label="Maior ano" value={topYear ? `${topYear.label} | ${topYear.bytes}` : "-"} />
        <Signal label="Maior formato" value={topExtension ? `${topExtension.label} | ${topExtension.bytes}` : "-"} />
        <Signal label="Dispositivo lider" value={topDevice ? `${topDevice.label} | ${formatNumber(topDevice.count)}` : "-"} />
      </div>
    </div>
  );
}

function GalleryTimeline({ items, onPick }: { items: TimelineBucket[]; onPick: (label: string) => void }) {
  const months = items.filter((item) => item.label && item.label !== "Sem data");
  const maxBytes = Math.max(...months.map((item) => item.bytesRaw), 0);
  const maxCount = Math.max(...months.map((item) => item.count), 0);
  const first = months[0]?.label ?? "-";
  const last = months[months.length - 1]?.label ?? "-";
  return (
    <div className="gallery-timeline">
      <div className="timeline-headline">
        <strong>{`${first} -> ${last}`}</strong>
        <span>{formatNumber(months.length)} meses com midia | barras por volume, linha por quantidade</span>
      </div>
      <div className="timeline-axis">
        {months.map((item) => {
          const byteHeight = maxBytes ? Math.max(10, Math.round((item.bytesRaw / maxBytes) * 92)) : 10;
          const countHeight = maxCount ? Math.max(8, Math.round((item.count / maxCount) * 70)) : 8;
          return (
            <button key={item.label} onClick={() => onPick(item.label)} title={`${item.label}: ${formatNumber(item.count)} arquivos, ${item.bytes}`}>
              <i style={{ height: byteHeight }} />
              <b style={{ height: countHeight }} />
              <span>{item.label.slice(5)}</span>
            </button>
          );
        })}
        {!months.length ? <EmptyState text="Sem datas catalogadas ainda." /> : null}
      </div>
      <div className="timeline-summary">
        {months.slice(-3).map((item) => (
          <Signal key={item.label} label={item.label} value={`${formatNumber(item.count)} arquivos | ${item.bytes}`} />
        ))}
      </div>
    </div>
  );
}

function deviceIconFor(label: string) {
  const value = label.toLowerCase();
  if (value.includes("dji") || value.includes("drone")) return Gauge;
  if (value.includes("iphone") || value.includes("samsung") || value.includes("sm-")) return Images;
  if (value.includes("adobe") || value.includes("lightroom")) return Sparkles;
  return Camera;
}

function DeviceBreakdown({ items, onPick }: { items: Bucket[]; onPick: (label: string) => void }) {
  const max = Math.max(...items.map((item) => item.count), 1);
  return (
    <div className="device-breakdown">
      {items.map((item) => {
        const Icon = deviceIconFor(item.label);
        const pct = Math.max(5, Math.round((item.count / max) * 100));
        return (
          <button key={item.label} onClick={() => onPick(item.label)}>
            <Icon size={15} />
            <span>{item.label}</span>
            <strong>{formatNumber(item.count)}</strong>
            <i><b style={{ width: `${pct}%` }} /></i>
          </button>
        );
      })}
      {!items.length ? <EmptyState text="Sem dispositivos detectados." /> : null}
    </div>
  );
}

function GalleryView({
  gallery,
  vault,
  imports,
  filter,
  sort,
  items,
  selectedItem,
  catalog,
  catalogBusy,
  galleryBusy,
  thumbsBusy,
  enrichBusy,
  onFilter,
  onSort,
  onClear,
  onSelect,
  onRefresh,
  onLoadMore,
  onHydrate,
  onEnrich,
  onOpenPath,
  onRevealPath,
  onSaveTags,
  onSaveNote,
}: {
  gallery: GalleryState;
  vault: Vault;
  imports: ImportItem[];
  filter: GalleryFilter;
  sort: GallerySort;
  items: GalleryItem[];
  selectedItem: GalleryItem | null;
  catalog: AssetCatalog | null;
  catalogBusy: boolean;
  galleryBusy: boolean;
  thumbsBusy: boolean;
  enrichBusy: boolean;
  onFilter: (filter: Partial<GalleryFilter>) => void;
  onSort: (sort: GallerySort) => void;
  onClear: () => void;
  onSelect: (id: number) => void;
  onRefresh: () => void;
  onLoadMore: () => void;
  onHydrate: () => void;
  onEnrich: () => void;
  onOpenPath: (path?: string) => void;
  onRevealPath: (path?: string) => void;
  onSaveTags: (assetId: number, tags: string[]) => void;
  onSaveNote: (assetId: number, body: string) => void;
}) {
  const [openFilter, setOpenFilter] = React.useState<string | null>(null);
  const totalBytes = items.reduce((sum, item) => sum + Number(item.sizeBytes || 0), 0);
  const visibleItems = items;
  const filteredTotal = gallery.filteredTotal ?? items.length;
  const hasMoreItems = Boolean(gallery.page?.hasMore);
  const typeOptions = gallery.breakdowns.media;
  const yearOptions = gallery.breakdowns.years;
  const monthOptions = gallery.breakdowns.months ?? [];
  const extensionOptions = gallery.breakdowns.extensions.map((item) => ({ ...item, label: `.${normalizeExtension(item.label)}` }));
  const deviceTypeOptions = gallery.breakdowns.deviceTypes ?? [];
  const deviceOptions = gallery.breakdowns.devices ?? [];
  const cameraOptions = gallery.breakdowns.cameras ?? [];
  const lensOptions = gallery.breakdowns.lenses ?? bucketsBy(gallery.items, (item) => item.lensModel || "Desconhecido", 10);
  const sizeOptions = gallery.breakdowns.sizes?.length
    ? gallery.breakdowns.sizes
    : [
      bucket("large", gallery.items.filter((item) => sizeBucketLabel(item) === "large")),
      bucket("medium", gallery.items.filter((item) => sizeBucketLabel(item) === "medium")),
      bucket("small", gallery.items.filter((item) => sizeBucketLabel(item) === "small")),
    ];
  const activeFilterCount = [
    filter.media,
    filter.year,
    filter.month,
    filter.extension,
    filter.deviceType,
    filter.device,
    filter.camera,
    filter.lens,
    filter.size,
    filter.problem,
  ].filter((value) => value !== "all").length + (filter.query.trim() ? 1 : 0);
  React.useEffect(() => {
    if (!openFilter) return;
    function close(event: MouseEvent) {
      if (!(event.target as Element).closest(".header-filter-menu")) setOpenFilter(null);
    }
    window.addEventListener("click", close);
    return () => window.removeEventListener("click", close);
  }, [openFilter]);
  return (
    <section className="gallery-layout">
      <div className="gallery-center">
        <div className="gallery-browser-header">
          <div className="gallery-heading">
            <span>{vault.name || "Galeria PhotoVault"}</span>
            <strong>{formatNumber(visibleItems.length)} de {formatNumber(items.length)} filtrados</strong>
          </div>
          <label className="gallery-search">
            <Search size={15} />
            <input value={filter.query} onChange={(event) => onFilter({ query: event.target.value })} placeholder="Buscar nome, pasta, câmera, lente..." />
          </label>
          <div className="header-filter-row">
            <HeaderFilterMenu id="media" openId={openFilter} onOpen={setOpenFilter} title="Tipo" active={filter.media} totalLabel="Todos" total={gallery.total} options={typeOptions} labelFor={mediaLabel} onPick={(value) => onFilter({ media: normalizeMediaLabel(value) })} />
            <HeaderFilterMenu id="year" openId={openFilter} onOpen={setOpenFilter} title="Ano" active={filter.year} totalLabel="Todos" total={gallery.total} options={yearOptions} onPick={(value) => onFilter({ year: value })} />
            <HeaderFilterMenu id="month" openId={openFilter} onOpen={setOpenFilter} title="Mes" active={filter.month} totalLabel="Todos" total={gallery.total} options={monthOptions} onPick={(value) => onFilter({ month: value })} />
            <HeaderFilterMenu id="extension" openId={openFilter} onOpen={setOpenFilter} title="Extensao" active={normalizeExtension(filter.extension) === "all" ? "all" : `.${normalizeExtension(filter.extension)}`} totalLabel="Todas" total={gallery.total} options={extensionOptions} onPick={(value) => onFilter({ extension: normalizeExtension(value) })} />
            <HeaderFilterMenu id="deviceType" openId={openFilter} onOpen={setOpenFilter} title="Classe" active={filter.deviceType} totalLabel="Todas" total={gallery.total} options={deviceTypeOptions} labelFor={deviceTypeLabel} onPick={(value) => onFilter({ deviceType: value })} />
            <HeaderFilterMenu id="device" openId={openFilter} onOpen={setOpenFilter} title="Dispositivo" active={filter.device} totalLabel="Todos" total={gallery.total} options={deviceOptions} onPick={(value) => onFilter({ device: value })} />
            <HeaderFilterMenu id="camera" openId={openFilter} onOpen={setOpenFilter} title="Camera" active={filter.camera} totalLabel="Todas" total={gallery.total} options={cameraOptions} onPick={(value) => onFilter({ camera: value })} />
            <HeaderFilterMenu id="lens" openId={openFilter} onOpen={setOpenFilter} title="Lente" active={filter.lens} totalLabel="Todas" total={gallery.total} options={lensOptions} onPick={(value) => onFilter({ lens: value })} />
            <HeaderFilterMenu id="size" openId={openFilter} onOpen={setOpenFilter} title="Tamanho" active={filter.size} totalLabel="Todos" total={filteredTotal} options={sizeOptions} labelFor={sizeLabel} onPick={(value) => onFilter({ size: value as GalleryFilter["size"] })} />
            <button className="ghost clear-header-filters" onClick={onClear} disabled={!activeFilterCount}><Filter size={15} /> Limpar {activeFilterCount ? `(${activeFilterCount})` : ""}</button>
          </div>
        </div>
        <div className="gallery-composition">
          <BigNumber label="Arquivos" value={formatNumber(filteredTotal)} detail={`${formatNumber(visibleItems.length)} renderizados agora`} />
          <BigNumber label="Tamanho" value={gallery.bytes} detail={`${formatBytes(totalBytes)} nesta visao`} />
          <BigNumber label="Periodo" value={dateRangeLabel(gallery)} detail={`${formatNumber(gallery.yearCount)} anos | ${formatNumber(gallery.monthCount)} meses`} />
          <BigNumber label="Formatos" value={formatNumber(gallery.extensionCount)} detail={`${formatNumber(gallery.breakdowns.devices?.length ?? 0)} origens tecnicas`} />
        </div>
        {!gallery.capabilities?.ffmpegAvailable ? (
          <div className="gallery-alert">
            <Film size={16} />
            <div>
              <strong>Frames de video indisponiveis</strong>
              <span>Instale as dependencias Python atualizadas para habilitar o extrator de frames. Fotos e RAW continuam com previews quando suportados.</span>
            </div>
          </div>
        ) : null}
        {!gallery.capabilities?.exiftoolAvailable ? (
          <div className="gallery-alert">
            <Sparkles size={16} />
            <div>
              <strong>Metadados ricos indisponiveis</strong>
              <span>{exiftoolStatusDetail(gallery)}</span>
            </div>
          </div>
        ) : null}
        <div className="gallery-toolbar">
          <div>
            <strong>{formatNumber(visibleItems.length)} de {formatNumber(filteredTotal)} itens</strong>
            <span>{formatBytes(totalBytes)} no filtro atual</span>
          </div>
          <div>
            <button className="ghost" onClick={onRefresh} disabled={galleryBusy}>Atualizar</button>
            <div className="sort-segment" aria-label="Ordenacao da galeria">
              <button className={sort === "date_desc" ? "active" : ""} onClick={() => onSort("date_desc")}>Recentes</button>
              <button className={sort === "date_asc" ? "active" : ""} onClick={() => onSort("date_asc")}>Antigas</button>
              <button className={sort === "size_desc" ? "active" : ""} onClick={() => onSort("size_desc")}>Tamanho</button>
              <button className={sort === "name_asc" ? "active" : ""} onClick={() => onSort("name_asc")}>Nome</button>
            </div>
            <span className="view-mode-pill"><ListChecks size={14} /> Explorer</span>
            <button className="primary" onClick={onHydrate} disabled={galleryBusy || thumbsBusy}><Images size={16} /> {thumbsBusy ? "Gerando..." : "Previews"}</button>
            <button className="primary" onClick={onEnrich} disabled={enrichBusy || !gallery.total}><Sparkles size={16} /> {enrichBusy ? "Lendo..." : "Metadados"}</button>
          </div>
        </div>
        {filter.month !== "all" ? (
          <div className="active-filter-row">
            <span>Mes filtrado: <strong>{filter.month}</strong></span>
            <button className="ghost" onClick={() => onFilter({ month: "all" })}>Limpar mes</button>
          </div>
        ) : null}
        <div className="media-explorer">
          <div className="media-explorer-head">
            <span>Arquivo</span>
            <span>Captura</span>
            <span>Origem</span>
            <span>Tamanho</span>
            <span>Status</span>
          </div>
          {visibleItems.map((item) => <MediaRow key={item.id} item={item} selected={selectedItem?.id === item.id} onClick={() => onSelect(item.id)} />)}
          {!items.length ? <EmptyState text={galleryBusy ? "Carregando galeria..." : "Nenhum item bate com os filtros atuais."} /> : null}
        </div>
        {hasMoreItems ? (
          <div className="load-more-row">
            <button className="secondary" onClick={onLoadMore} disabled={galleryBusy}>
              <Layers3 size={15} /> Carregar mais {formatNumber(Math.min(GALLERY_PAGE_SIZE, Math.max(filteredTotal - visibleItems.length, 0)))}
            </button>
          </div>
        ) : null}
      </div>

      <aside className="inspector">
        <SectionTitle eyebrow="Detalhe" title={selectedItem?.name ?? "Selecione um item"} />
        <div className="preview-stage">
          {selectedItem ? (
            <SmartImage path={selectedItem.thumbnail} status={selectedItem.previewStatus} alt={selectedItem.name} icon={isVideo(selectedItem) ? Film : Camera} />
          ) : (
            <div><ImageOff size={38} /> Preview indisponivel</div>
          )}
        </div>
        <div className="metadata-drawers">
          <MetadataDrawer title="Arquivo" open>
            <MetaLine label="Tipo" value={selectedItem?.mediaType} />
            <MetaLine label="Extensao" value={selectedItem?.extension} />
            <MetaLine label="Formato" value={selectedItem?.fileType || selectedItem?.mimeType} />
            <MetaLine label="Tamanho" value={selectedItem?.size} />
            <MetaLine label="Data" value={selectedItem?.date || "sem data"} />
            <MetaLine label="Resolucao" value={selectedItem?.resolution} />
          </MetadataDrawer>
          <MetadataDrawer title="Camera" open>
            <MetaLine label="Dispositivo" value={selectedItem?.deviceName} />
            <MetaLine label="Classe" value={deviceTypeLabel(selectedItem?.deviceType)} />
            <MetaLine label="Fabricante" value={selectedItem?.cameraMake} />
            <MetaLine label="Modelo" value={selectedItem?.cameraModel} />
            <MetaLine label="Lente" value={selectedItem?.lensModel} />
            <MetaLine label="Software" value={selectedItem?.software} />
          </MetadataDrawer>
          <MetadataDrawer title="Captura" open>
            <MetaLine label="ISO" value={selectedItem?.iso} />
            <MetaLine label="Abertura" value={selectedItem?.aperture ? `f/${formatDecimal(selectedItem.aperture, 1)}` : ""} />
            <MetaLine label="Obturador" value={formatExposure(selectedItem?.shutterSpeed)} />
            <MetaLine label="Distancia focal" value={selectedItem?.focalLength ? `${formatDecimal(selectedItem.focalLength, 1)} mm` : ""} />
          </MetadataDrawer>
          <MetadataDrawer title="Video">
            <MetaLine label="Codec" value={selectedItem?.codec} />
            <MetaLine label="Bitrate" value={formatBitrate(selectedItem?.bitrate)} />
            <MetaLine label="Frame rate" value={selectedItem?.frameRate ? `${formatDecimal(selectedItem.frameRate, 2)} fps` : ""} />
          </MetadataDrawer>
          <MetadataDrawer title="Localizacao">
            <MetaLine label="GPS" value={selectedItem?.gpsLatitude && selectedItem?.gpsLongitude ? `${selectedItem.gpsLatitude}, ${selectedItem.gpsLongitude}` : ""} />
          </MetadataDrawer>
          <MetadataDrawer title="Catalogo">
            <MetaLine label="Origem metadata" value={metadataBadge(selectedItem)} />
            <MetaLine label="Asset ID" value={selectedItem?.assetId} />
            <MetaLine label="Instancia" value={selectedItem?.id} />
            <MetaLine label="Tags" value={catalog?.tags.join(", ") || selectedItem?.tags} />
            <MetaLine label="Notas" value={catalog?.notes.length ?? selectedItem?.noteCount} />
          </MetadataDrawer>
          <CatalogEditor
            item={selectedItem}
            catalog={catalog}
            busy={catalogBusy}
            onSaveTags={onSaveTags}
            onSaveNote={onSaveNote}
          />
        </div>
        <div className="inspector-actions">
          <button className="secondary" onClick={() => onRevealPath(selectedItem?.path)} disabled={!selectedItem?.path}><FolderOpen size={15} /> Localizar</button>
          <button className="secondary" onClick={() => onOpenPath(selectedItem?.path)} disabled={!selectedItem?.path}><ExternalLink size={15} /> Abrir</button>
        </div>
        <p className="path-copy">{selectedItem?.path ?? "Aguardando selecao"}</p>
      </aside>
    </section>
  );
}

function ImportView({
  vault,
  sourcePath,
  busy,
  progress,
  progressVisible,
  disk,
  onVault,
  onSource,
  onPickFolder,
  onOpenPath,
  onSave,
  onAnalyze,
  onExecute,
  onReset,
  onDismissProgress,
  canExecute,
  capacityWarning,
}: {
  vault: Vault;
  sourcePath: string;
  busy: boolean;
  progress: ProgressInfo | null;
  progressVisible: boolean;
  disk: Disk;
  onVault: (vault: Vault) => void;
  onSource: (value: string) => void;
  onPickFolder: (target: "vault" | "source") => void;
  onOpenPath: (path?: string) => void;
  onSave: () => void;
  onAnalyze: () => void;
  onExecute: () => void;
  onReset: () => void;
  onDismissProgress: () => void;
  canExecute: boolean;
  capacityWarning: string;
}) {
  return (
    <section className="import-layout">
      <div className="panel span-2">
        <SectionTitle eyebrow="Configuracao" title="Origem e vault" />
        <div className="form-grid">
          <label className="wide">
            <span>Nome da galeria</span>
            <input value={vault.name} onChange={(event) => onVault({ ...vault, name: event.target.value })} placeholder="Ex: Arquivo da Familia" />
          </label>
          <label>
            <span>Vault</span>
            <div className="input-actions">
              <input value={vault.path} onChange={(event) => onVault({ ...vault, path: event.target.value })} placeholder="Diretorio fixo da galeria" />
              <button type="button" className="icon-button" onClick={() => onPickFolder("vault")} title="Selecionar vault"><FolderOpen size={15} /></button>
              <button type="button" className="icon-button" onClick={() => onOpenPath(vault.path)} disabled={!vault.path} title="Abrir vault"><ExternalLink size={15} /></button>
            </div>
          </label>
          <label>
            <span>Padrao</span>
            <select value={PATTERN_PRESETS.some((item) => item.value === vault.pattern) ? vault.pattern : "custom"} onChange={(event) => event.target.value !== "custom" && onVault({ ...vault, pattern: event.target.value })}>
              {PATTERN_PRESETS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
              <option value="custom">Personalizado</option>
            </select>
            <input value={vault.pattern} onChange={(event) => onVault({ ...vault, pattern: event.target.value })} placeholder="{year}/{month:02d}" />
          </label>
          <label className="wide">
            <span>Origem</span>
            <div className="input-actions">
              <input value={sourcePath} onChange={(event) => onSource(event.target.value)} placeholder="Pasta de origem para nova importacao" />
              <button type="button" className="icon-button" onClick={() => onPickFolder("source")} title="Selecionar origem"><FolderOpen size={15} /></button>
              <button type="button" className="icon-button" onClick={() => onOpenPath(sourcePath)} disabled={!sourcePath} title="Abrir origem"><ExternalLink size={15} /></button>
            </div>
          </label>
        </div>
        <div className="actions">
          <button className="secondary" onClick={onSave} disabled={busy}><Save size={16} /> Salvar vault</button>
          <button className="primary" onClick={onAnalyze} disabled={busy}><FolderInput size={17} /> Analisar origem</button>
          <button className="secondary" onClick={onExecute} disabled={busy || !canExecute}><Play size={17} /> Executar plano</button>
          <button className="danger" onClick={onReset} disabled={busy}><RotateCcw size={16} /> Reset local</button>
        </div>
        {capacityWarning ? <CapacityAlert message={capacityWarning} /> : null}
      </div>
      <div className="panel">
        <SectionTitle eyebrow="Armazenamento" title="Destino da importacao" />
        <ImportStorageMeter disk={disk} />
      </div>
      {progressVisible ? (
        <div className="panel">
          <SectionTitle eyebrow="Progresso" title={progress?.status === "running" ? "Rodando" : "Resultado"} />
          <ProgressPanel progress={progress} embedded onDismiss={onDismissProgress} />
          <p className="path-copy">{progress?.path || "Sem processo em andamento."}</p>
        </div>
      ) : null}
    </section>
  );
}

function ReviewsView({
  imports,
  selectedImport,
  importInsights,
  counts,
  busy,
  duplicateRate,
  onSelectImport,
  onBulk,
  onDecision,
  onExecute,
  canExecute,
  capacityWarning,
}: {
  imports: ImportItem[];
  selectedImport: ImportItem | null;
  importInsights: ImportInsights;
  counts: Record<Decision, number>;
  busy: boolean;
  duplicateRate: number;
  onSelectImport: (item: ImportItem) => void;
  onBulk: (decision: Decision) => void;
  onDecision: (group: DecisionGroup, decision: Decision) => void;
  onExecute: () => void;
  canExecute: boolean;
  capacityWarning: string;
}) {
  return (
    <section className="reviews-layout">
      <aside className="timeline">
        <SectionTitle eyebrow="Historico" title="Importacoes" />
        {imports.map((item) => (
          <button className={`import-card ${selectedImport?.id === item.id ? "active" : ""}`} key={item.id} onClick={() => onSelectImport(item)}>
            <span className={`status ${item.status}`}>{statusLabel(item.status)}</span>
            <strong>{item.name}</strong>
            <p>{formatNumber(item.fresh)} novos | {formatNumber(item.duplicates)} duplicados | {item.bytes}</p>
          </button>
        ))}
        {!imports.length ? <EmptyState text="Nenhuma importacao ainda." /> : null}
      </aside>
      <div className="review-main">
        <section className="overview compact">
          <Metric icon={Archive} label="Encontrados" value={formatNumber(selectedImport?.found ?? 0)} caption={selectedImport?.source ?? "-"} />
          <Metric icon={CheckCircle2} label="Importar" value={formatNumber(counts.import)} caption={selectedImport?.bytes ?? "0 B"} />
          <Metric icon={Trash2} label="Ignorar" value={formatNumber(counts.skip)} caption={`${duplicateRate}% duplicidade`} />
          <Metric icon={AlertTriangle} label="Revisar" value={formatNumber(counts.review)} caption="decisao pendente" />
        </section>
        <div className="panel">
          <SectionTitle eyebrow="Decisoes" title={`${counts.import} importar | ${counts.skip} ignorar | ${counts.review} revisar`} />
          <DecisionLegend counts={counts} />
          {capacityWarning ? <CapacityAlert message={capacityWarning} /> : null}
          <div className="actions">
            <button className="secondary" onClick={() => onBulk("import")} disabled={busy}><CheckCircle2 size={15} /> Importar grupos</button>
            <button className="secondary" onClick={() => onBulk("skip")} disabled={busy}><Trash2 size={15} /> Ignorar grupos</button>
            <button className="secondary" onClick={() => onBulk("review")} disabled={busy}><FileWarning size={15} /> Revisar grupos</button>
            <button className="primary" onClick={onExecute} disabled={busy || !canExecute}><Play size={15} /> Executar</button>
          </div>
          <DecisionCockpit groups={importInsights.reasonGroups} busy={busy} onDecision={onDecision} />
        </div>
      </div>
    </section>
  );
}

function CapacityAlert({ message }: { message: string }) {
  return (
    <div className="capacity-alert">
      <HardDrive size={16} />
      <div>
        <strong>Capacidade do destino</strong>
        <span>{message}</span>
      </div>
    </div>
  );
}

function JobsView({
  health,
  progress,
  progressVisible,
  logPath,
  onRefresh,
  onDismissProgress,
  onViewLogs,
  onJobAction,
}: {
  health: HealthState;
  progress: ProgressInfo | null;
  progressVisible: boolean;
  logPath: string;
  onRefresh: () => void;
  onDismissProgress: () => void;
  onViewLogs: () => void;
  onJobAction: (jobId: number, action: "pause" | "resume" | "cancel") => void;
}) {
  const recentJobs = health.recentJobs ?? [];
  const summary = Object.entries(health.jobs ?? {}).flatMap(([kind, statuses]) =>
    Object.entries(statuses).map(([status, count]) => ({ kind, status, count })),
  );
  const running = summary.filter((item) => item.status === "running").reduce((sum, item) => sum + item.count, 0);
  const paused = summary.filter((item) => item.status === "paused").reduce((sum, item) => sum + item.count, 0);
  const failures = summary.filter((item) => ["error", "failed"].includes(item.status)).reduce((sum, item) => sum + item.count, 0);
  const cancelled = summary.filter((item) => item.status === "cancelled").reduce((sum, item) => sum + item.count, 0);
  const completed = summary.filter((item) => item.status === "done").reduce((sum, item) => sum + item.count, 0);
  return (
    <section className="jobs-layout">
      <div className="panel span-2">
        <SectionTitle eyebrow="Fila operacional" title="Jobs da galeria" action="Atualizar" onAction={onRefresh} />
        <div className="job-summary-grid">
          <BigNumber label="Rodando" value={formatNumber(running)} detail="processos ativos agora" />
          <BigNumber label="Pausados" value={formatNumber(paused)} detail="aguardando retomada" />
          <BigNumber label="Concluidos" value={formatNumber(completed)} detail="historico registrado" />
          <BigNumber label="Cancelados" value={formatNumber(cancelled)} detail="interrompidos pelo usuario" />
          <BigNumber label="Falhas" value={formatNumber(failures)} detail="precisam revisao" />
        </div>
        {progressVisible ? (
          <div className="job-live-progress">
            <SectionTitle eyebrow="Agora" title={progress?.status === "running" ? "Processando" : "Ultimo resultado"} />
            <ProgressPanel progress={progress} embedded onDismiss={onDismissProgress} />
            <p className="path-copy">{progress?.path || "Sem processo em andamento."}</p>
          </div>
        ) : (
          <EmptyState text="Nenhum processo em andamento agora." />
        )}
      </div>
      <div className="panel">
        <SectionTitle eyebrow="Resumo por tipo" title={`${formatNumber(summary.length)} estados`} />
        <div className="job-kind-grid">
          {summary.map((item) => (
            <article key={`${item.kind}-${item.status}`} className={item.status}>
              <span>{jobKindLabel(item.kind)}</span>
              <strong>{formatNumber(item.count)}</strong>
              <em>{jobStatusLabel(item.status)}</em>
            </article>
          ))}
          {!summary.length ? <EmptyState text="Nenhum job registrado ainda." /> : null}
        </div>
      </div>
      <div className="panel span-2">
        <SectionTitle eyebrow="Historico" title="Ultimas execucoes" action="Abrir logs" onAction={onViewLogs} />
        <div className="job-list">
          {recentJobs.map((job) => <JobRow key={job.id} job={job} onAction={onJobAction} />)}
          {!recentJobs.length ? <EmptyState text="Sem jobs no historico local." /> : null}
        </div>
      </div>
    </section>
  );
}

function JobRow({ job, onAction }: { job: BackgroundJob; onAction: (jobId: number, action: "pause" | "resume" | "cancel") => void }) {
  const canPause = ["running", "queued"].includes(job.status);
  const canResume = job.status === "paused";
  const canCancel = ["running", "queued", "paused"].includes(job.status);
  return (
    <article className={`job-row ${job.status}`}>
      <div>
        <span className={`status ${job.status}`}>{jobStatusLabel(job.status)}</span>
        <strong>{jobKindLabel(job.kind)}</strong>
        <em>{formatJobTime(job.updated_at || job.completed_at || job.started_at || job.created_at)}</em>
      </div>
      <p>{job.error || jobPayloadSummary(job.payload) || `${job.entity_type || "galeria"} ${job.entity_id ?? ""}`}</p>
      <div className="job-actions">
        {canPause ? <button className="secondary" onClick={() => onAction(job.id, "pause")}><Clock3 size={14} /> Pausar</button> : null}
        {canResume ? <button className="secondary" onClick={() => onAction(job.id, "resume")}><Play size={14} /> Retomar</button> : null}
        {canCancel ? <button className="danger" onClick={() => onAction(job.id, "cancel")}><Trash2 size={14} /> Cancelar</button> : null}
      </div>
    </article>
  );
}

function jobKindLabel(value?: string) {
  return { analysis: "Analise de importacao", import: "Importacao", metadata: "Metadados", previews: "Previews" }[value || ""] ?? (value || "Job");
}

function jobStatusLabel(value?: string) {
  return { queued: "Na fila", running: "Rodando", paused: "Pausado", done: "Concluido", warning: "Aviso", error: "Erro", failed: "Falhou", cancelled: "Cancelado" }[value || ""] ?? (value || "Pendente");
}

function jobPayloadSummary(payload?: Record<string, unknown>) {
  if (!payload) return "";
  const parts = [
    payload.found !== undefined ? `${formatNumber(Number(payload.found))} encontrados` : "",
    payload.new !== undefined ? `${formatNumber(Number(payload.new))} novos` : "",
    payload.duplicates !== undefined ? `${formatNumber(Number(payload.duplicates))} duplicados` : "",
    payload.count !== undefined ? `${formatNumber(Number(payload.count))} itens` : "",
    payload.enriched !== undefined ? `${formatNumber(Number(payload.enriched))} enriquecidos` : "",
    payload.errors !== undefined ? `${formatNumber(Number(payload.errors))} erros` : "",
  ].filter(Boolean);
  return parts.join(" | ");
}

function formatJobTime(value?: string) {
  if (!value) return "sem data";
  return value.slice(0, 19).replace("T", " ");
}

function LogsView({ logs, logPath, onRefresh }: { logs: LogState; logPath: string; onRefresh: () => void }) {
  return (
    <section className="panel logs-panel">
      <SectionTitle eyebrow="Log local" title={logs.logPath || logPath || "Sem log"} action="Atualizar" onAction={onRefresh} />
      <pre>{logs.lines.length ? logs.lines.join("\n") : "Nenhuma linha carregada."}</pre>
    </section>
  );
}

function dateRangeLabel(gallery: GalleryState) {
  if (!gallery.firstDate && !gallery.lastDate) return "sem datas";
  if (gallery.firstDate?.slice(0, 4) === gallery.lastDate?.slice(0, 4)) return gallery.firstDate.slice(0, 4);
  return `${gallery.firstDate?.slice(0, 4) || "?"}-${gallery.lastDate?.slice(0, 4) || "?"}`;
}

function GalleryIdentity({
  vault,
  gallery,
  disk,
  savings,
  compact = false,
}: {
  vault: Vault;
  gallery: GalleryState;
  disk?: Disk;
  savings?: DuplicateSavings;
  compact?: boolean;
}) {
  return (
    <section className={compact ? "gallery-identity compact" : "gallery-identity"}>
      <div>
        <p>Galeria permanente</p>
        <h2>{vault.name || "Galeria PhotoVault"}</h2>
        <span>{vault.path || "Vault nao configurado"}</span>
      </div>
      <div className="identity-stats">
        <BigNumber label="Acervo" value={gallery.bytes} detail={`${formatNumber(gallery.total)} arquivos`} />
        <BigNumber label="Midias" value={`${formatNumber(gallery.photos + gallery.videos)}`} detail={`${formatNumber(gallery.photos)} fotos | ${formatNumber(gallery.videos)} videos`} />
        <BigNumber label="Periodo" value={dateRangeLabel(gallery)} detail={`${formatNumber(gallery.monthCount)} meses`} />
        {!compact ? <BigNumber label="Disponivel" value={formatBytes(disk?.free ?? 0)} detail="livre no disco da galeria" /> : null}
        {!compact ? <BigNumber label="Criada em" value={formatDateShort(vault.createdAt)} detail="data de criacao do vault" /> : null}
        {!compact ? <BigNumber label="Economia" value={savings?.bytes ?? "0 B"} detail={`${formatNumber(savings?.count ?? 0)} duplicatas evitadas`} /> : null}
      </div>
    </section>
  );
}

function BigNumber({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <article className="big-number">
      <span>{label}</span>
      <strong>{value}</strong>
      <em>{detail}</em>
    </article>
  );
}

function ImportStorageMeter({ disk }: { disk: Disk }) {
  const usedPct = disk.total ? Math.min((disk.used / disk.total) * 100, 100) : 0;
  const pendingPct = disk.total ? Math.min((disk.pending / disk.total) * 100, Math.max(100 - usedPct, 0)) : 0;
  const freePct = disk.total ? Math.max(100 - usedPct, 0) : 0;
  return (
    <div className="storage-meter">
      <div className="storage-track" aria-label="Capacidade do destino">
        <span className="used" style={{ width: `${usedPct}%` }} />
        <span className="pending" style={{ left: `${usedPct}%`, width: `${pendingPct}%` }} />
      </div>
      <Signal label="Livre no destino" value={`${formatBytes(disk.free)} (${Math.round(freePct)}%)`} tone={freePct > 15 ? "good" : "bad"} />
      <Signal label="Usado no disco" value={`${formatBytes(disk.used)} (${Math.round(usedPct)}%)`} />
      <Signal label="Plano pendente" value={formatBytes(disk.pending)} />
    </div>
  );
}

function DiagnosticsPanel({ diagnostics }: { diagnostics: DiagnosticsState }) {
  const required = diagnostics.tools.filter((item) => item.required);
  const optional = diagnostics.tools.filter((item) => !item.required);
  return (
    <div className="diagnostics-panel">
      <div className="diagnostics-summary">
        <Terminal size={17} />
        <div>
          <strong>{diagnostics.summary}</strong>
          <span>
            {diagnostics.platform?.system || "Sistema"} {diagnostics.platform?.release || ""} | {diagnostics.requiredMissing} obrigatorios ausentes | {diagnostics.optionalMissing} opcionais ausentes
          </span>
        </div>
      </div>
      <div className="diagnostic-grid">
        {[...required, ...optional].map((item) => (
          <div className={`diagnostic-item ${item.status}`} key={item.label}>
            <span>{item.label}</span>
            <strong>{diagnosticValue(item)}</strong>
            <em>{item.path || item.detail || (item.required ? "Obrigatorio" : "Opcional")}</em>
          </div>
        ))}
      </div>
      <div className="diagnostic-paths">
        {diagnostics.paths.map((item) => (
          <Signal key={item.label} label={item.label} value={item.detail || item.path} tone={item.status === "ok" ? "good" : "bad"} />
        ))}
      </div>
    </div>
  );
}

function GalleryHealthPanel({ health, onFilter, onView }: { health: HealthState; onFilter: (filter: Partial<GalleryFilter>) => void; onView: (view: View) => void }) {
  return (
    <div className="health-panel">
      <Signal label="Metadados pendentes" value={formatNumber(health.metadataPending)} tone={health.metadataPending ? "bad" : "good"} />
      <Signal label="Sem data" value={formatNumber(health.withoutDate)} tone={health.withoutDate ? "bad" : "good"} />
      <Signal label="Videos grandes" value={formatNumber(health.largeVideos)} />
      <Signal label="Imports retomaveis" value={formatNumber(health.resumableImports?.length ?? 0)} tone={health.resumableImports?.length ? "bad" : "good"} />
      <div className="health-actions">
        <button className="secondary" onClick={() => onFilter({ problem: "without-date" })}>Sem data</button>
        <button className="secondary" onClick={() => onFilter({ problem: "video", size: "large" })}>Videos</button>
        <button className="secondary" onClick={() => onView("reviews")}>Imports</button>
      </div>
      <div className="health-insights">
        {(health.insights ?? []).slice(0, 3).map((item) => (
          <article key={item.title}>
            <strong>{item.title}</strong>
            <span>{item.detail}</span>
          </article>
        ))}
        {!health.insights?.length ? <EmptyState text="Nenhum alerta operacional relevante agora." /> : null}
      </div>
      {health.resumableImports?.length ? (
        <div className="resumable-list">
          {health.resumableImports.slice(0, 3).map((item) => (
            <article key={item.id}>
              <strong>{item.name}</strong>
              <span>{formatNumber(item.resumable)} pendentes | {formatNumber(item.done)} concluidos | {formatNumber(item.errors)} erros</span>
            </article>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function CatalogEditor({
  item,
  catalog,
  busy,
  onSaveTags,
  onSaveNote,
}: {
  item: GalleryItem | null;
  catalog: AssetCatalog | null;
  busy: boolean;
  onSaveTags: (assetId: number, tags: string[]) => void;
  onSaveNote: (assetId: number, body: string) => void;
}) {
  const [tagsText, setTagsText] = React.useState("");
  const [noteText, setNoteText] = React.useState("");
  React.useEffect(() => {
    setTagsText((catalog?.tags ?? (item?.tags ? item.tags.split(",").map((value) => value.trim()).filter(Boolean) : [])).join(", "));
    setNoteText("");
  }, [item?.assetId, catalog?.tags.join("|")]);
  if (!item) return null;
  const tags = tagsText.split(",").map((value) => value.trim()).filter(Boolean);
  return (
    <MetadataDrawer title="Curadoria" open>
      <div className="catalog-editor">
        <label>
          <span>Tags</span>
          <input value={tagsText} onChange={(event) => setTagsText(event.target.value)} placeholder="familia, viagem, drone" />
        </label>
        <button className="secondary" disabled={busy} onClick={() => onSaveTags(item.assetId, tags)}><Tag size={14} /> Salvar tags</button>
        <label>
          <span>Nova nota</span>
          <input value={noteText} onChange={(event) => setNoteText(event.target.value)} placeholder="Observacao de curadoria" />
        </label>
        <button className="secondary" disabled={busy || !noteText.trim()} onClick={() => {
          onSaveNote(item.assetId, noteText);
          setNoteText("");
        }}>Adicionar nota</button>
        <div className="note-list">
          {(catalog?.notes ?? []).slice(0, 3).map((note) => (
            <article key={note.id}>
              <strong>{note.created_at?.slice(0, 16).replace("T", " ")}</strong>
              <span>{note.body}</span>
            </article>
          ))}
        </div>
      </div>
    </MetadataDrawer>
  );
}

function HeaderFilterMenu({
  id,
  openId,
  onOpen,
  title,
  active,
  totalLabel,
  total,
  options,
  labelFor = (value: string) => value,
  onPick,
}: {
  id: string;
  openId: string | null;
  onOpen: (id: string | null) => void;
  title: string;
  active: string;
  totalLabel: string;
  total: number;
  options: Bucket[];
  labelFor?: (value: string) => string;
  onPick: (value: string) => void;
}) {
  const activeOption = options.find((item) => item.label.toLowerCase() === active.toLowerCase());
  const activeLabel = active === "all" ? totalLabel : labelFor(activeOption?.label ?? active);
  const open = openId === id;
  function pick(value: string) {
    onPick(value);
    onOpen(null);
  }
  return (
    <div className={open ? "header-filter-menu open" : "header-filter-menu"}>
      <button className="header-filter-summary" onClick={(event) => {
        event.stopPropagation();
        onOpen(open ? null : id);
      }}>
        <span>{title}</span>
        <strong>{activeLabel}</strong>
      </button>
      {open ? (
        <div className="header-filter-popover" onClick={(event) => event.stopPropagation()}>
          <button className={active === "all" ? "active" : ""} onClick={() => pick("all")}>
            <span>{totalLabel}</span>
            <strong>{formatNumber(total)}</strong>
          </button>
          {options.filter((item) => item.count > 0).map((item) => {
            const isActive = active.toLowerCase() === item.label.toLowerCase();
            return (
              <button key={item.label} className={isActive ? "active" : ""} onClick={() => pick(item.label)}>
                <span>{labelFor(item.label)}</span>
                <strong>{formatNumber(item.count)}</strong>
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}

function TimelineStrip({ items, active, onPick }: { items: Bucket[]; active: string; onPick: (label: string) => void }) {
  const max = Math.max(...items.map((item) => item.count), 0);
  return (
    <div className="timeline-strip">
      {items.map((item) => {
        const height = max ? Math.max(12, Math.round((item.count / max) * 72)) : 12;
        const isActive = active === item.label || active === item.label.slice(0, 4);
        return (
          <button key={item.label} className={isActive ? "active" : ""} onClick={() => onPick(item.label)}>
            <i style={{ height }} />
            <strong>{item.label}</strong>
            <span>{formatNumber(item.count)} | {item.bytes}</span>
          </button>
        );
      })}
      {!items.length ? <EmptyState text="Sem datas catalogadas ainda." /> : null}
    </div>
  );
}

function ImportLog({ imports }: { imports: ImportItem[] }) {
  return (
    <div className="gallery-import-log">
      {imports.slice(0, 4).map((item) => (
        <article key={item.id}>
          <span className={`status ${item.status}`}>{statusLabel(item.status)}</span>
          <div>
            <strong>{item.name}</strong>
            <p>{item.date || "sem data"} | {formatNumber(item.fresh)} novos | {formatNumber(item.duplicates)} duplicados | {item.bytes}</p>
          </div>
        </article>
      ))}
      {!imports.length ? <EmptyState text="Nenhuma importacao registrada ainda." /> : null}
    </div>
  );
}

function Metric({ icon: Icon, label, value, caption }: { icon: React.ElementType; label: string; value: string; caption: string }) {
  return (
    <article className="metric">
      <Icon size={18} />
      <span>{label}</span>
      <strong>{value}</strong>
      <em>{caption}</em>
    </article>
  );
}

function SectionTitle({ eyebrow, title, action, onAction }: { eyebrow: string; title: string; action?: string; onAction?: () => void }) {
  return (
    <div className="section-title">
      <div><p>{eyebrow}</p><h2>{title}</h2></div>
      {action ? <button className="ghost" onClick={onAction}>{action}</button> : null}
    </div>
  );
}

type InsightAction = {
  icon: React.ElementType;
  title: string;
  value: string;
  detail: string;
  action: string;
  onClick: () => void;
};

function InsightGroup({ title, detail, items }: { title: string; detail: string; items: InsightAction[] }) {
  return (
    <div className="insight-group">
      <div className="insight-group-heading">
        <strong>{title}</strong>
        <span>{detail}</span>
      </div>
      <div className="insight-pair">
        {items.map((item) => (
          <InsightCard key={item.title} {...item} />
        ))}
      </div>
    </div>
  );
}

function InsightCard({ icon: Icon, title, value, detail, action, onClick }: { icon: React.ElementType; title: string; value: string; detail: string; action: string; onClick: () => void }) {
  return (
    <button className="insight-card tone-neutral" onClick={onClick}>
      <Icon size={19} />
      <span>{title}</span>
      <strong>{value}</strong>
      <em>{detail}</em>
      <b>{action}</b>
    </button>
  );
}

function FacetButtons({ items, onPick, labelFor = (label: string) => label }: { items: Bucket[]; onPick: (label: string) => void; labelFor?: (label: string) => string }) {
  const total = items.reduce((sum, item) => sum + item.count, 0);
  return (
    <div className="facet-buttons">
      {items.map((item) => {
        const pct = total ? Math.max(6, Math.round((item.count / total) * 100)) : 0;
        return (
          <button key={item.label} className={`tone-${facetTone(item.label)}`} onClick={() => onPick(item.label)}>
            <div><strong>{labelFor(item.label)}</strong><span>{formatNumber(item.count)} | {item.bytes}</span></div>
            <i><b style={{ width: `${pct}%` }} /></i>
          </button>
        );
      })}
      {!items.length ? <EmptyState text="Sem dados suficientes." /> : null}
    </div>
  );
}

function mediaColor(label: string) {
  const value = normalizeMediaLabel(label);
  if (value === "photo") return "var(--photo)";
  if (value === "video" || value === "movie") return "var(--video)";
  return "var(--neutral-bar)";
}

function MediaDistribution({ items, onPick }: { items: Bucket[]; onPick: (label: string) => void }) {
  const totalCount = items.reduce((sum, item) => sum + item.count, 0);
  const totalBytes = items.reduce((sum, item) => sum + item.bytesRaw, 0);
  const ordered = [...items].sort((a, b) => b.count - a.count);
  if (!ordered.length) return <EmptyState text="Sem midias catalogadas." />;
  let cursor = 0;
  const segments = ordered.map((item) => {
    const start = cursor;
    const pct = totalCount ? (item.count / totalCount) * 100 : 0;
    cursor += pct;
    return `${mediaColor(item.label)} ${start}% ${cursor}%`;
  });
  return (
    <div className="media-distribution">
      <div className="media-donut-wrap">
        <div
          className="media-donut"
          style={{ background: `conic-gradient(${segments.join(", ")})` }}
          aria-label="Distribuicao por quantidade de arquivos"
        >
          <div>
            <strong>{formatNumber(totalCount)}</strong>
            <span>arquivos</span>
          </div>
        </div>
        <div className="media-donut-summary">
          <strong>{formatBytes(totalBytes)}</strong>
          <span>catalogados nas midias filtradas</span>
        </div>
      </div>
      <div className="media-legend">
        {ordered.map((item) => {
          const countPct = totalCount ? Math.round((item.count / totalCount) * 100) : 0;
          const bytePct = totalBytes ? Math.round((item.bytesRaw / totalBytes) * 100) : 0;
          return (
            <button key={item.label} onClick={() => onPick(item.label)}>
              <i style={{ background: mediaColor(item.label) }} />
              <span>{mediaLabel(item.label)}</span>
              <strong>{countPct}%</strong>
              <em>{formatNumber(item.count)} arquivos | {bytePct}% bytes</em>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function BarChart({ items, mode = "count", onPick }: { items: Bucket[]; mode?: "count" | "bytes"; onPick: (label: string) => void }) {
  const max = Math.max(...items.map((item) => (mode === "bytes" ? item.bytesRaw : item.count)), 0);
  return (
    <div className="bar-chart">
      {items.map((item) => {
        const value = mode === "bytes" ? item.bytesRaw : item.count;
        const pct = max ? Math.max(5, Math.round((value / max) * 100)) : 0;
        return (
          <button key={item.label} className={mode === "bytes" ? "tone-storage" : `tone-${facetTone(item.label)}`} onClick={() => onPick(item.label)}>
            <span>{item.label}</span>
            <i><b style={{ width: `${pct}%` }} /></i>
            <strong>{mode === "bytes" ? item.bytes : formatNumber(item.count)}</strong>
          </button>
        );
      })}
      {!items.length ? <EmptyState text="Sem dados suficientes." /> : null}
    </div>
  );
}

function FilterGroup({ title, children }: { title: string; children: React.ReactNode }) {
  return <div className="filter-group"><h3>{title}</h3><div>{children}</div></div>;
}

function CleanFilterGroup({
  title,
  totalLabel,
  active,
  total,
  options,
  labelFor = (value: string) => value,
  onPick,
}: {
  title: string;
  totalLabel: string;
  active: string;
  total: number;
  options: Bucket[];
  labelFor?: (value: string) => string;
  onPick: (value: string) => void;
}) {
  const max = Math.max(total, ...options.map((item) => item.count), 1);
  return (
    <div className="clean-filter-group">
      <h3>{title}</h3>
      <button className={active === "all" ? "active" : ""} onClick={() => onPick("all")}>
        <span>{totalLabel}</span>
        <strong>{formatNumber(total)}</strong>
        <i><b style={{ width: "100%" }} /></i>
      </button>
      {options.filter((item) => item.count > 0).map((item) => {
        const isActive = active.toLowerCase() === item.label.toLowerCase();
        const pct = Math.max(4, Math.round((item.count / max) * 100));
        return (
          <button key={item.label} className={isActive ? "active" : ""} onClick={() => onPick(item.label)}>
            <span>{labelFor(item.label)}</span>
            <strong>{formatNumber(item.count)}</strong>
            <i><b style={{ width: `${pct}%` }} /></i>
          </button>
        );
      })}
    </div>
  );
}

function Chip({ active, children, onClick }: { active: boolean; children: React.ReactNode; onClick: () => void }) {
  return <button className={active ? "chip active" : "chip"} onClick={onClick}>{children}</button>;
}

function MediaRow({ item, selected, onClick }: { item: GalleryItem; selected: boolean; onClick: () => void }) {
  const previewLabel = item.previewStatus === "placeholder" ? "placeholder" : item.previewStatus === "missing" ? "sem preview" : "preview";
  const Icon = isVideo(item) ? Film : Camera;
  return (
    <button className={`media-row ${selected ? "active" : ""}`} onClick={onClick} title={item.path}>
      <div className="media-row-file">
        <span className={isVideo(item) ? "media-row-icon video" : "media-row-icon photo"}><Icon size={17} /></span>
        <div>
          <strong>{item.name}</strong>
          <em>{item.mediaType} {normalizeExtension(item.extension).toUpperCase() || "MIDIA"} | {item.resolution}</em>
        </div>
      </div>
      <span>{item.date || "sem data"}</span>
      <span>{item.deviceName || "Desconhecido"}</span>
      <span>{item.size}</span>
      <div className="media-row-badges">
        <b>{normalizeExtension(item.extension).toUpperCase() || "MIDIA"}</b>
        {isRaw(item) ? <b>RAW</b> : null}
        {item.metadataSource === "ExifTool" ? <b>EXIF</b> : null}
        <b className={item.previewStatus === "ready" ? "ok" : ""}>{previewLabel}</b>
      </div>
    </button>
  );
}

function SmartImage({ path, status, alt, icon: Icon }: { path?: string; status?: string; alt: string; icon: React.ElementType }) {
  const [failed, setFailed] = React.useState(false);
  React.useEffect(() => setFailed(false), [path]);
  if (!path || failed || status === "placeholder") {
    return (
      <div className={`image-fallback ${status === "placeholder" ? "placeholder" : ""}`}>
        <Icon size={26} />
        <small>{status === "placeholder" ? "placeholder" : failed ? "falhou" : "sem preview"}</small>
      </div>
    );
  }
  return <img src={convertFileSrc(path)} alt={alt} draggable={false} onError={() => setFailed(true)} />;
}

function Signal({ label, value, tone }: { label: string; value: string; tone?: "good" | "bad" }) {
  return (
    <div className={`signal ${tone ?? ""}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function MetadataDrawer({ title, children, open = false }: { title: string; children: React.ReactNode; open?: boolean }) {
  return (
    <details className="metadata-drawer" open={open}>
      <summary>{title}</summary>
      <div>{children}</div>
    </details>
  );
}

function MetaLine({ label, value }: { label: string; value: unknown }) {
  const text = cleanMeta(value) || "-";
  return (
    <div className="meta-line">
      <span>{label}</span>
      <strong>{text}</strong>
    </div>
  );
}

function DecisionLegend({ counts }: { counts: Record<Decision, number> }) {
  return (
    <div className="decision-legend">
      <span className="import"><CheckCircle2 size={14} /> Importar <b>{formatNumber(counts.import)}</b></span>
      <span className="skip"><Trash2 size={14} /> Ignorar <b>{formatNumber(counts.skip)}</b></span>
      <span className="review"><FileWarning size={14} /> Revisar <b>{formatNumber(counts.review)}</b></span>
    </div>
  );
}

function DecisionCockpit({ groups, busy, onDecision }: { groups: DecisionGroup[]; busy: boolean; onDecision: (group: DecisionGroup, decision: Decision) => void }) {
  return (
    <div className="decision-cockpit">
      {groups.map((group) => (
        <article className={`decision-card ${group.decision}`} key={`${group.reason}-${group.mediaType}-${group.status}`}>
          <div>
            <span>{group.mediaType} | {group.status}</span>
            <strong>{group.label}</strong>
            <em>{formatNumber(group.count)} arquivos | {group.bytes}</em>
          </div>
          <div className="decision-actions">
            <button title="Marcar grupo para importar" aria-label="Marcar grupo para importar" className={group.decision === "import" ? "active import" : "import"} onClick={() => onDecision(group, "import")} disabled={busy}><CheckCircle2 size={14} /></button>
            <button title="Marcar grupo para ignorar" aria-label="Marcar grupo para ignorar" className={group.decision === "skip" ? "active skip" : "skip"} onClick={() => onDecision(group, "skip")} disabled={busy}><Trash2 size={14} /></button>
            <button title="Marcar grupo para revisar" aria-label="Marcar grupo para revisar" className={group.decision === "review" ? "active review" : "review"} onClick={() => onDecision(group, "review")} disabled={busy}><FileWarning size={14} /></button>
          </div>
        </article>
      ))}
      {!groups.length ? <EmptyState text="Nenhum grupo de decisao nesta importacao. Analise uma origem para criar grupos acionaveis." /> : null}
    </div>
  );
}

function ProgressPanel({ progress, embedded = false, onDismiss }: { progress: ProgressInfo | null; embedded?: boolean; onDismiss?: () => void }) {
  const current = progress?.current ?? 0;
  const total = progress?.total ?? 0;
  const ratio = total ? Math.min(current / total, 1) : progress?.status === "running" ? 0.18 : 0;
  const metrics = progress?.metrics;
  const pct = Math.round(ratio * 100);
  const eta = metrics?.etaSeconds ? `${Math.ceil(metrics.etaSeconds / 60)} min` : "-";
  return (
    <section className={embedded ? "progress-panel embedded" : "progress-panel"}>
      <div className="progress-head">
        <strong>{progress?.status === "running" ? `${pct}%` : progress?.status === "done" ? "Concluido" : "Pronto"}</strong>
        <span>{total ? `${formatNumber(current)} / ${formatNumber(total)}` : progress?.stage ?? "idle"}</span>
        {onDismiss && progress?.status !== "running" ? (
          <button className="ghost compact-button" onClick={onDismiss}>Descartar</button>
        ) : null}
      </div>
      <div className={progress?.status === "running" ? "progress-track running" : "progress-track"}><i style={{ width: `${ratio * 100}%` }} /></div>
      <p>{progress?.message ?? "Sem processo em andamento."}</p>
      {metrics?.steps?.length ? (
        <div className="progress-step-row">
          {metrics.steps.map((step) => (
            <span key={step.id} className={`progress-step ${step.status}`}>
              <b>{step.label}</b>
              <em>{progressStepLabel(step.status)}</em>
            </span>
          ))}
        </div>
      ) : null}
      {metrics ? (
        <div className="progress-metrics">
          <span><b>{(metrics.throughputMbps ?? 0).toFixed(1)}</b> MB/s</span>
          <span><b>{formatBytes(metrics.bytesImported ?? 0)}</b> copiados</span>
          <span><b>{eta}</b> ETA</span>
          <span><b>{(metrics.lastFileMbps ?? 0).toFixed(1)}</b> MB/s ultimo</span>
        </div>
      ) : null}
    </section>
  );
}

function progressStepLabel(status?: string) {
  return {
    pending: "Pendente",
    running: "Rodando",
    paused: "Pausado",
    done: "OK",
    warning: "Aviso",
    error: "Erro",
    failed: "Erro",
    cancelled: "Cancelado",
  }[status || ""] ?? (status || "-");
}

function EmptyState({ text }: { text: string }) {
  return <div className="empty-state">{text}</div>;
}

ReactDOM.createRoot(document.getElementById("root")!).render(<App />);
