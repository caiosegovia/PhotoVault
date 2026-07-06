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
  Trash2,
  Video,
} from "lucide-react";
import {
  filterGalleryItems,
  hasMissingPreview,
  isRaw,
  isVideo,
  itemMonth,
  itemYear,
  normalizeExtension,
  normalizeMedia,
  type GalleryFilter,
  type GalleryItem,
} from "./galleryFilters";
import "./styles.css";

type ImportStatus = "ready" | "done" | "running" | "failed";
type Decision = "import" | "skip" | "review";
type View = "cockpit" | "gallery" | "import" | "reviews" | "logs";

type ImportItem = {
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

type Vault = { id?: number; name: string; path: string; pattern: string };
type Disk = { total: number; used: number; free: number; pending: number };

type Bucket = { label: string; count: number; bytes: string; bytesRaw: number };
type GalleryBreakdowns = { media: Bucket[]; years: Bucket[]; months: Bucket[]; extensions: Bucket[]; deviceTypes?: Bucket[]; devices?: Bucket[]; cameras?: Bucket[] };
type GalleryState = {
  items: GalleryItem[];
  total: number;
  photos: number;
  videos: number;
  withoutDate: number;
  bytes: string;
  bytesTotal: number;
  firstDate: string;
  lastDate: string;
  yearCount: number;
  monthCount: number;
  extensionCount: number;
  breakdowns: GalleryBreakdowns;
  capabilities?: { ffmpegAvailable?: boolean; exiftoolAvailable?: boolean; exiftoolVersion?: string };
  timings?: Record<string, number>;
};

type DecisionGroup = {
  reason: string;
  label: string;
  decision: Decision;
  mediaType: string;
  status: string;
  count: number;
  bytes: string;
  bytesRaw: number;
};
type ImportInsights = { reasonGroups: DecisionGroup[]; mediaGroups: Bucket[]; statusGroups: Bucket[] };
type ProgressInfo = {
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
type ProgressMetrics = {
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
type CopyFileMetric = { path: string; bytes: number; seconds: number; mbps: number };
type BackendState = {
  vault: Vault;
  imports: ImportItem[];
  importInsights: ImportInsights;
  gallery: GalleryState;
  disk: Disk;
  progress?: ProgressInfo;
  logPath?: string;
};
type LogState = { logPath: string; lines: string[] };

const EMPTY_GALLERY: GalleryState = {
  items: [],
  total: 0,
  photos: 0,
  videos: 0,
  withoutDate: 0,
  bytes: "0 B",
  bytesTotal: 0,
  firstDate: "",
  lastDate: "",
  yearCount: 0,
  monthCount: 0,
  extensionCount: 0,
  breakdowns: { media: [], years: [], months: [], extensions: [], deviceTypes: [], devices: [], cameras: [] },
  capabilities: { ffmpegAvailable: false, exiftoolAvailable: false },
};
const EMPTY_IMPORT_INSIGHTS: ImportInsights = { reasonGroups: [], mediaGroups: [], statusGroups: [] };
const DEFAULT_FILTER: GalleryFilter = {
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

const PATTERN_PRESETS = [
  { label: "Ano / mes", value: "{year}/{month:02d}" },
  { label: "Ano / mes / tipo", value: "{year}/{month:02d}/{media_type}" },
  { label: "Ano / camera", value: "{year}/{camera_make}" },
  { label: "Ano / extensao", value: "{year}/{extension}" },
  { label: "Mes compacto", value: "{year}-{month:02d}" },
];
const CAPACITY_RESERVE_BYTES = 1024 ** 3;
const GALLERY_ITEM_LIMIT = 50000;

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
  return { large: "Grandes", small: "Leves", all: "Todos" }[value || ""] ?? value ?? "";
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

function App() {
  const [activeView, setActiveView] = React.useState<View>("cockpit");
  const [imports, setImports] = React.useState<ImportItem[]>([]);
  const [importInsights, setImportInsights] = React.useState<ImportInsights>(EMPTY_IMPORT_INSIGHTS);
  const [gallery, setGallery] = React.useState<GalleryState>(EMPTY_GALLERY);
  const [vault, setVault] = React.useState<Vault>({ name: "Galeria PhotoVault", path: "", pattern: "{year}/{month:02d}" });
  const [disk, setDisk] = React.useState<Disk>({ total: 0, used: 0, free: 0, pending: 0 });
  const [selectedImportId, setSelectedImportId] = React.useState<number | null>(null);
  const [selectedGalleryId, setSelectedGalleryId] = React.useState<number | null>(null);
  const [sourcePath, setSourcePath] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [thumbsBusy, setThumbsBusy] = React.useState(false);
  const [enrichBusy, setEnrichBusy] = React.useState(false);
  const [message, setMessage] = React.useState("Carregando estado real do PhotoVault...");
  const [progress, setProgress] = React.useState<ProgressInfo | null>(null);
  const [logPath, setLogPath] = React.useState("");
  const [logs, setLogs] = React.useState<LogState>({ logPath: "", lines: [] });
  const [filter, setFilter] = React.useState<GalleryFilter>(DEFAULT_FILTER);
  const progressTimerRef = React.useRef<number | null>(null);

  const selectedImport = imports.find((item) => item.id === selectedImportId) ?? imports[0] ?? null;

  React.useEffect(() => {
    loadState();
    return () => stopProgressPolling();
  }, []);

  React.useEffect(() => {
    if (activeView === "logs") refreshLogs();
  }, [activeView]);

  const filteredItems = React.useMemo(() => {
    return filterGalleryItems(gallery.items, filter);
  }, [gallery.items, filter]);
  const selectedGalleryItem = filteredItems.find((item) => item.id === selectedGalleryId) ?? filteredItems[0] ?? null;

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
  const usedPct = disk.total ? Math.min((disk.used / disk.total) * 100, 100) : 0;
  const pendingPct = disk.total ? Math.min((disk.pending / disk.total) * 100, 100 - usedPct) : 0;
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
    ? `Plano restante ${formatBytes(pendingPlanBytes)} + reserva ${formatBytes(CAPACITY_RESERVE_BYTES)}. Livre no destino: ${formatBytes(disk.free)}. Faltam ${formatBytes(capacityShortfall)}.`
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
      setLogPath(state.logPath ?? state.progress?.logPath ?? "");
      setSelectedImportId(preferredImportId ?? selectedImportId ?? state.imports[0]?.id ?? null);
      setSelectedGalleryId((current) => current ?? state.gallery?.items[0]?.id ?? null);
      setMessage(state.imports.length ? "Estado carregado do banco real." : "Configure o vault e crie a primeira importacao.");
      hydrateThumbnails(state.gallery ?? EMPTY_GALLERY);
    } catch (error) {
      setMessage(`Erro ao carregar backend: ${String(error)}`);
    }
  }

  async function hydrateThumbnails(currentGallery: GalleryState) {
    if (!currentGallery.total || thumbsBusy) return;
    const missing = currentGallery.items.some((item) => !item.thumbnail);
    if (!missing) return;
    setThumbsBusy(true);
    try {
      const result = await callBridge<GalleryState>("gallery", { limit: GALLERY_ITEM_LIMIT, ensureThumbnails: true });
      setGallery(result);
      setSelectedGalleryId((current) => current ?? result.items[0]?.id ?? null);
    } catch (error) {
      setMessage(`Nao consegui gerar previews: ${String(error)}`);
    } finally {
      setThumbsBusy(false);
    }
  }

  async function refreshGallery(ensureThumbnails = false) {
    setThumbsBusy(ensureThumbnails);
    try {
      const result = await callBridge<GalleryState>("gallery", { limit: GALLERY_ITEM_LIMIT, ensureThumbnails });
      setGallery(result);
      setSelectedGalleryId((current) => current ?? result.items[0]?.id ?? null);
      setMessage(ensureThumbnails ? "Previews atualizados." : "Galeria atualizada.");
    } catch (error) {
      setMessage(`Erro ao atualizar galeria: ${String(error)}`);
    } finally {
      setThumbsBusy(false);
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

  function bulkDecision(decision: Decision) {
    if (!selectedImport?.id) return;
    Promise.all(importInsights.reasonGroups.map((group) => persistGroupDecision(group, decision)));
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
    startProgressPolling();
    try {
      await callBridge("execute_import", { planId: selectedImport.planId, verifyMode: "size" });
      await loadState(selectedImport.id);
      setActiveView("gallery");
      setMessage("Importacao executada.");
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
    startProgressPolling();
    try {
      const state = await callBridge<BackendState>("enrich_metadata", { limit: 2000 });
      setVault(state.vault);
      setImports(state.imports);
      setImportInsights(state.importInsights ?? EMPTY_IMPORT_INSIGHTS);
      setGallery(state.gallery ?? EMPTY_GALLERY);
      setDisk(state.disk);
      setProgress(state.progress ?? null);
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
      const result = await callBridge<{ progress: ProgressInfo; logPath: string }>("progress");
      setProgress(result.progress);
      setLogPath(result.logPath || result.progress.logPath || "");
      if (result.progress.status === "running") setMessage(result.progress.message);
    } catch (error) {
      setMessage(`Erro ao ler progresso: ${String(error)}`);
    }
  }

  function startProgressPolling() {
    stopProgressPolling();
    let ticks = 0;
    const timer = window.setInterval(async () => {
      ticks += 1;
      await refreshProgress();
      if (ticks > 720) stopProgressPolling();
    }, 1000);
    progressTimerRef.current = timer;
    window.setTimeout(() => {
      if (progressTimerRef.current === timer) stopProgressPolling();
    }, 12 * 60 * 1000);
  }

  function stopProgressPolling() {
    if (progressTimerRef.current !== null) {
      window.clearInterval(progressTimerRef.current);
      progressTimerRef.current = null;
    }
  }

  function patchFilter(next: Partial<GalleryFilter>) {
    setFilter((current) => {
      const merged = { ...current, ...next };
      if (
        next.media !== undefined ||
        next.year !== undefined ||
        next.extension !== undefined ||
        next.device !== undefined ||
        next.size !== undefined
      ) {
        merged.month = next.month ?? "all";
      }
      if (next.year !== undefined && next.year === "all") merged.month = "all";
      if (next.month !== undefined && next.month !== "all") merged.year = next.month.slice(0, 4);
      if (next.device !== undefined) {
        merged.deviceType = "all";
        merged.camera = "all";
      }
      if (next.media !== undefined || next.year !== undefined || next.extension !== undefined || next.device !== undefined || next.size !== undefined) {
        merged.problem = next.problem ?? "all";
      }
      return merged;
    });
    setActiveView("gallery");
  }

  const nav = [
    { id: "cockpit" as View, label: "Cockpit", icon: Gauge },
    { id: "gallery" as View, label: "Galeria", icon: Images },
    { id: "import" as View, label: "Importar", icon: FolderInput },
    { id: "reviews" as View, label: "Revisoes", icon: ListChecks },
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
        <div className="rail-section">
          <span>Disco</span>
          <strong>{formatBytes(disk.free)} livres</strong>
          <div className="capacity">
            <span style={{ width: `${usedPct}%` }} />
            <i style={{ left: `${usedPct}%`, width: `${pendingPct}%` }} />
          </div>
        </div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow"><Layers3 size={15} /> {activeView}</p>
            <h1>{headline(activeView, gallery, selectedImport, vault)}</h1>
            <p>{message}</p>
          </div>
          <ProgressPanel progress={progress} />
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
            enrichBusy={enrichBusy}
            onFilter={patchFilter}
            onView={setActiveView}
            onEnrich={enrichMetadata}
          />
        ) : null}

        {activeView === "gallery" ? (
          <GalleryView
            gallery={gallery}
            vault={vault}
            disk={disk}
            imports={imports}
            filter={filter}
            items={filteredItems}
            selectedItem={selectedGalleryItem}
            thumbsBusy={thumbsBusy}
            enrichBusy={enrichBusy}
            onFilter={patchFilter}
            onClear={() => setFilter(DEFAULT_FILTER)}
            onSelect={setSelectedGalleryId}
            onRefresh={() => refreshGallery(false)}
            onHydrate={() => refreshGallery(true)}
            onEnrich={enrichMetadata}
            onOpenPath={openPath}
            onRevealPath={revealPath}
          />
        ) : null}

        {activeView === "import" ? (
          <ImportView
            vault={vault}
            sourcePath={sourcePath}
            busy={busy}
            progress={progress}
            onVault={setVault}
            onSource={setSourcePath}
            onPickFolder={pickFolder}
            onOpenPath={openPath}
            onSave={saveVault}
            onAnalyze={analyzeImport}
            onExecute={executeSelected}
            onReset={resetAll}
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

        {activeView === "logs" ? <LogsView logs={logs} logPath={logPath} onRefresh={refreshLogs} /> : null}
      </section>
    </main>
  );
}

function headline(view: View, gallery: GalleryState, selectedImport: ImportItem | null, vault: Vault) {
  if (view === "gallery") return vault.name || `${formatNumber(gallery.total)} arquivos preservados`;
  if (view === "import") return "Nova importacao";
  if (view === "reviews") return selectedImport ? `Revisao de ${selectedImport.name}` : "Revisoes de importacao";
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
  enrichBusy,
  onFilter,
  onView,
  onEnrich,
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
  enrichBusy: boolean;
  onFilter: (filter: Partial<GalleryFilter>) => void;
  onView: (view: View) => void;
  onEnrich: () => void;
}) {
  const videoShare = gallery.bytesTotal ? Math.round((gallery.breakdowns.media.find((item) => item.label === "video")?.bytesRaw ?? 0) / gallery.bytesTotal * 100) : 0;
  const galleryDiskShare = disk.total ? Math.min(Math.round((gallery.bytesTotal / disk.total) * 100), 100) : 0;
  return (
    <div className="view-stack">
      <GalleryIdentity vault={vault} gallery={gallery} disk={disk} />

      <section className="overview">
        <Metric icon={Archive} label="Na galeria" value={formatNumber(gallery.total)} caption={gallery.bytes} />
        <Metric icon={Camera} label="Fotos" value={formatNumber(gallery.photos)} caption={`${formatNumber(gallery.withoutDate)} sem data`} />
        <Metric icon={Video} label="Videos" value={formatNumber(gallery.videos)} caption={formatBytes(largeVideoBytes)} />
        <Metric icon={CalendarDays} label="Periodo" value={dateRangeLabel(gallery)} caption={`${formatNumber(gallery.monthCount)} meses catalogados`} />
      </section>

      <section className="overview">
        <Metric icon={HardDrive} label="Peso do acervo" value={gallery.bytes} caption={`${galleryDiskShare}% do disco do vault`} />
        <Metric icon={Layers3} label="Agrupadores" value={formatNumber(gallery.extensionCount)} caption={`${formatNumber(gallery.yearCount)} anos | ${formatNumber(gallery.breakdowns.devices?.length ?? 0)} dispositivos`} />
        <Metric icon={CheckCircle2} label="Duplicatas evitadas" value={formatNumber(duplicateTotal)} caption={`${formatNumber(importedTotal)} novos`} />
        <Metric icon={Database} label="Importado" value={formatBytes(importedBytesTotal)} caption={`${formatNumber(imports.length)} ciclos registrados`} />
      </section>

      <section className="cockpit-grid">
        <div className="panel span-2">
          <SectionTitle eyebrow="Inteligencia da galeria" title="Atalhos de curadoria" />
          <div className="insight-grid">
            <InsightCard icon={ImageOff} title="Sem preview" value={formatNumber(missingThumbCount)} detail="Gerar thumbs ou validar midias quebradas" action="Filtrar" onClick={() => onFilter({ problem: "missing-thumb" })} />
            <InsightCard icon={CalendarDays} title="Sem data" value={formatNumber(gallery.withoutDate)} detail="Arquivos que podem cair fora da timeline" action="Ver" onClick={() => onFilter({ problem: "without-date" })} />
            <InsightCard icon={Sparkles} title="RAW" value={formatNumber(rawCount)} detail="Originais pesados para curadoria fina" action="Abrir" onClick={() => onFilter({ problem: "raw" })} />
            <InsightCard icon={Film} title="Videos grandes" value={formatBytes(largeVideoBytes)} detail="Consumo relevante de vault" action="Revisar" onClick={() => onFilter({ problem: "video", size: "large" })} />
          </div>
        </div>

        <div className="panel">
          <SectionTitle eyebrow="Distribuicao" title="Midia" />
          <DonutSummary value={videoShare} label="peso em video" />
          <FacetButtons items={gallery.breakdowns.media} onPick={(label) => onFilter({ media: label })} />
        </div>

        <div className="panel">
          <SectionTitle eyebrow="Armazenamento" title="Disco do vault" />
          <StorageMeter disk={disk} gallery={gallery} />
        </div>

        <div className="panel">
          <SectionTitle eyebrow="Timeline" title="Meses com mais acervo" />
          <BarChart items={gallery.breakdowns.months} onPick={(label) => onFilter({ month: label })} />
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
          <BarChart items={gallery.breakdowns.devices ?? []} onPick={(label) => onFilter({ device: label, problem: "all" })} />
        </div>

        <div className="panel">
          <SectionTitle eyebrow="Captura" title="Cameras catalogadas" />
          <FacetButtons items={gallery.breakdowns.cameras ?? []} onPick={(label) => onFilter({ camera: label, problem: "all" })} />
        </div>

        <div className="panel">
          <SectionTitle eyebrow="Metadados" title="Enriquecimento" />
          <Signal
            label="ExifTool"
            value={gallery.capabilities?.exiftoolAvailable ? `Disponivel ${gallery.capabilities?.exiftoolVersion ?? ""}`.trim() : "Ausente"}
            tone={gallery.capabilities?.exiftoolAvailable ? "good" : "bad"}
          />
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

        <div className="panel">
          <SectionTitle eyebrow="Risco operacional" title="Sinais" />
          <Signal label="Erros acumulados" value={formatNumber(errorTotal)} tone={errorTotal ? "bad" : "good"} />
          <Signal label="Ultimo plano" value={selectedImport ? statusLabel(selectedImport.status) : "Sem plano"} />
          <Signal label="Bytes novos" value={formatBytes(importedBytesTotal)} />
          <Signal label="ffmpeg" value={gallery.capabilities?.ffmpegAvailable ? "Disponivel" : "Ausente"} tone={gallery.capabilities?.ffmpegAvailable ? "good" : "bad"} />
          <Signal label="ExifTool" value={gallery.capabilities?.exiftoolAvailable ? "Disponivel" : "Ausente"} tone={gallery.capabilities?.exiftoolAvailable ? "good" : "bad"} />
        </div>
      </section>
    </div>
  );
}

function GalleryView({
  gallery,
  vault,
  disk,
  imports,
  filter,
  items,
  selectedItem,
  thumbsBusy,
  enrichBusy,
  onFilter,
  onClear,
  onSelect,
  onRefresh,
  onHydrate,
  onEnrich,
  onOpenPath,
  onRevealPath,
}: {
  gallery: GalleryState;
  vault: Vault;
  disk: Disk;
  imports: ImportItem[];
  filter: GalleryFilter;
  items: GalleryItem[];
  selectedItem: GalleryItem | null;
  thumbsBusy: boolean;
  enrichBusy: boolean;
  onFilter: (filter: Partial<GalleryFilter>) => void;
  onClear: () => void;
  onSelect: (id: number) => void;
  onRefresh: () => void;
  onHydrate: () => void;
  onEnrich: () => void;
  onOpenPath: (path?: string) => void;
  onRevealPath: (path?: string) => void;
}) {
  const totalBytes = items.reduce((sum, item) => sum + Number(item.sizeBytes || 0), 0);
  const facetBase: GalleryFilter = { ...filter, month: "all", problem: "all", deviceType: "all", camera: "all" };
  const typeContext = filterGalleryItems(gallery.items, { ...facetBase, media: "all" });
  const yearContext = filterGalleryItems(gallery.items, { ...facetBase, year: "all" });
  const extensionContext = filterGalleryItems(gallery.items, { ...facetBase, extension: "all" });
  const deviceContext = filterGalleryItems(gallery.items, { ...facetBase, device: "all" });
  const sizeContext = filterGalleryItems(gallery.items, { ...facetBase, size: "all" });
  const typeOptions = bucketsBy(typeContext, (item) => normalizeMediaLabel(item.mediaType), 4);
  const yearOptions = bucketsBy(yearContext, itemYear, 8);
  const extensionOptions = bucketsBy(extensionContext, (item) => `.${normalizeExtension(item.extension)}`, 10);
  const deviceOptions = bucketsBy(deviceContext, (item) => item.deviceName || "Desconhecido", 10);
  const monthOptions = bucketsBy(filterGalleryItems(gallery.items, { ...facetBase, month: "all" }), itemMonth, 18);
  const sizeOptions = [
    bucket("large", sizeContext.filter((item) => sizeBucketLabel(item) === "large")),
    bucket("small", sizeContext.filter((item) => sizeBucketLabel(item) === "small")),
  ];
  return (
    <section className="gallery-layout">
      <aside className="filter-panel">
        <SectionTitle eyebrow="Filtros" title={`${formatNumber(items.length)} exibidos`} />
        <label className="search-box">
          <Search size={15} />
          <input value={filter.query} onChange={(event) => onFilter({ query: event.target.value })} placeholder="Buscar nome, pasta, data..." />
        </label>
        <CleanFilterGroup title="Tipo" totalLabel="Todos" active={filter.media} total={typeContext.length} options={typeOptions} labelFor={mediaLabel} onPick={(value) => onFilter({ media: value })} />
        <CleanFilterGroup title="Ano" totalLabel="Todos" active={filter.year} total={yearContext.length} options={yearOptions} onPick={(value) => onFilter({ year: value })} />
        <CleanFilterGroup title="Extensao" totalLabel="Todas" active={normalizeExtension(filter.extension) === "all" ? "all" : `.${normalizeExtension(filter.extension)}`} total={extensionContext.length} options={extensionOptions} onPick={(value) => onFilter({ extension: normalizeExtension(value) })} />
        <CleanFilterGroup title="Dispositivo" totalLabel="Todos" active={filter.device} total={deviceContext.length} options={deviceOptions} onPick={(value) => onFilter({ device: value })} />
        <CleanFilterGroup title="Tamanho" totalLabel="Todos" active={filter.size} total={sizeContext.length} options={sizeOptions} labelFor={sizeLabel} onPick={(value) => onFilter({ size: value as GalleryFilter["size"] })} />
        <button className="ghost full" onClick={onClear}><Filter size={15} /> Limpar filtros</button>
      </aside>

      <div className="gallery-center">
        <GalleryIdentity vault={vault} gallery={gallery} disk={disk} compact />
        <div className="gallery-composition">
          <BigNumber label="Arquivos" value={formatNumber(gallery.total)} detail={`${formatNumber(items.length)} exibidos agora`} />
          <BigNumber label="Tamanho" value={gallery.bytes} detail={`${formatBytes(totalBytes)} nesta visao`} />
          <BigNumber label="Periodo" value={dateRangeLabel(gallery)} detail={`${formatNumber(gallery.yearCount)} anos | ${formatNumber(gallery.monthCount)} meses`} />
          <BigNumber label="Formatos" value={formatNumber(gallery.extensionCount)} detail={`${formatNumber(gallery.breakdowns.devices?.length ?? 0)} origens tecnicas`} />
        </div>
        <div className="gallery-story">
          <section>
            <SectionTitle eyebrow="Composicao" title="Do que a galeria e feita" />
            <FacetButtons items={gallery.breakdowns.media} onPick={(label) => onFilter({ media: label })} />
          </section>
          <section>
            <SectionTitle eyebrow="Timeline" title="Meses preservados" />
            <TimelineStrip items={monthOptions} active={filter.month} onPick={(label) => onFilter({ month: label })} />
          </section>
          <section>
            <SectionTitle eyebrow="Importacoes" title="Como ela chegou aqui" />
            <ImportLog imports={imports} />
          </section>
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
              <span>Instale o ExifTool para melhorar cameras, lentes, datas e sinais tecnicos. O catalogo atual continua funcionando.</span>
            </div>
          </div>
        ) : null}
        <div className="gallery-toolbar">
          <div>
            <strong>{formatNumber(items.length)} itens</strong>
            <span>{formatBytes(totalBytes)} nesta visao</span>
          </div>
          <div>
            <button className="ghost" onClick={onRefresh}>Atualizar</button>
            <button className="primary" onClick={onHydrate} disabled={thumbsBusy}><Images size={16} /> {thumbsBusy ? "Gerando..." : "Previews"}</button>
            <button className="primary" onClick={onEnrich} disabled={enrichBusy || !gallery.total}><Sparkles size={16} /> {enrichBusy ? "Lendo..." : "Metadados"}</button>
          </div>
        </div>
        {filter.month !== "all" ? (
          <div className="active-filter-row">
            <span>Mes filtrado: <strong>{filter.month}</strong></span>
            <button className="ghost" onClick={() => onFilter({ month: "all" })}>Limpar mes</button>
          </div>
        ) : null}
        <div className="media-grid">
          {items.map((item) => <MediaTile key={item.id} item={item} selected={selectedItem?.id === item.id} onClick={() => onSelect(item.id)} />)}
          {!items.length ? <EmptyState text="Nenhum item bate com os filtros atuais." /> : null}
        </div>
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
        <div className="meta-list">
          <Signal label="Tipo" value={selectedItem?.mediaType ?? "-"} />
          <Signal label="Extensao" value={selectedItem?.extension ?? "-"} />
          <Signal label="Data" value={selectedItem?.date ?? "sem data"} />
          <Signal label="Resolucao" value={selectedItem?.resolution ?? "-"} />
          <Signal label="Classe" value={deviceTypeLabel(selectedItem?.deviceType)} />
          <Signal label="Dispositivo" value={selectedItem?.deviceName ?? "-"} />
          <Signal label="Camera" value={`${selectedItem?.cameraMake ?? ""} ${selectedItem?.cameraModel ?? ""}`.trim() || "-"} />
          <Signal label="Tamanho" value={selectedItem?.size ?? "0 B"} />
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
  onVault,
  onSource,
  onPickFolder,
  onOpenPath,
  onSave,
  onAnalyze,
  onExecute,
  onReset,
  canExecute,
  capacityWarning,
}: {
  vault: Vault;
  sourcePath: string;
  busy: boolean;
  progress: ProgressInfo | null;
  onVault: (vault: Vault) => void;
  onSource: (value: string) => void;
  onPickFolder: (target: "vault" | "source") => void;
  onOpenPath: (path?: string) => void;
  onSave: () => void;
  onAnalyze: () => void;
  onExecute: () => void;
  onReset: () => void;
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
        <SectionTitle eyebrow="Progresso" title={progress?.status === "running" ? "Rodando" : "Pronto"} />
        <ProgressPanel progress={progress} embedded />
        <p className="path-copy">{progress?.path || "Sem processo em andamento."}</p>
      </div>
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
    <div className="gallery-alert capacity-alert">
      <HardDrive size={18} />
      <div>
        <strong>Espaco insuficiente no destino</strong>
        <span>{message}</span>
      </div>
    </div>
  );
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

function GalleryIdentity({ vault, gallery, disk, compact = false }: { vault: Vault; gallery: GalleryState; disk: Disk; compact?: boolean }) {
  return (
    <section className={compact ? "gallery-identity compact" : "gallery-identity"}>
      <div>
        <p>Galeria permanente</p>
        <h2>{vault.name || "Galeria PhotoVault"}</h2>
        <span>{vault.path || "Vault nao configurado"}</span>
      </div>
      <div className="identity-stats">
        <BigNumber label="Acervo" value={gallery.bytes} detail={`${formatNumber(gallery.total)} arquivos`} />
        <BigNumber label="Disponivel" value={formatBytes(disk.free)} detail={`${formatBytes(disk.used)} usados no disco`} />
        <BigNumber label="Periodo" value={dateRangeLabel(gallery)} detail={`${formatNumber(gallery.monthCount)} meses`} />
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

function StorageMeter({ disk, gallery }: { disk: Disk; gallery: GalleryState }) {
  const usedPct = disk.total ? Math.min((disk.used / disk.total) * 100, 100) : 0;
  const galleryPct = disk.total ? Math.min((gallery.bytesTotal / disk.total) * 100, 100) : 0;
  const freePct = disk.total ? Math.max(100 - usedPct, 0) : 0;
  return (
    <div className="storage-meter">
      <div className="storage-track" aria-label="Uso do disco">
        <span className="used" style={{ width: `${usedPct}%` }} />
        <span className="gallery" style={{ width: `${galleryPct}%` }} />
      </div>
      <Signal label="Acervo PhotoVault" value={`${gallery.bytes} (${Math.round(galleryPct)}%)`} />
      <Signal label="Usado no disco" value={`${formatBytes(disk.used)} (${Math.round(usedPct)}%)`} />
      <Signal label="Disponivel" value={`${formatBytes(disk.free)} (${Math.round(freePct)}%)`} tone={freePct > 15 ? "good" : "bad"} />
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

function DonutSummary({ value, label }: { value: number; label: string }) {
  const bounded = Math.max(0, Math.min(value, 100));
  return (
    <div className="donut-summary">
      <div style={{ background: `conic-gradient(var(--accent) ${bounded}%, #0b0d0d 0)` }}>
        <strong>{bounded}%</strong>
      </div>
      <span>{label}</span>
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

function MediaTile({ item, selected, onClick }: { item: GalleryItem; selected: boolean; onClick: () => void }) {
  const previewLabel = item.previewStatus === "placeholder" ? "placeholder" : item.previewStatus === "missing" ? "sem preview" : "preview";
  return (
    <button className={`media-tile ${selected ? "active" : ""}`} onClick={onClick} title={item.path}>
      <div className="tile-image">
        <SmartImage path={item.thumbnail} status={item.previewStatus} alt={item.name} icon={isVideo(item) ? Film : Camera} />
        <span>{isVideo(item) ? <Film size={13} /> : <Camera size={13} />}</span>
      </div>
      <div className="tile-meta">
        <em>{item.mediaType} {item.extension} | {previewLabel}</em>
        <strong>{item.name}</strong>
        <p>{item.date || "sem data"} | {item.size}</p>
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

function ProgressPanel({ progress, embedded = false }: { progress: ProgressInfo | null; embedded?: boolean }) {
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
      </div>
      <div className={progress?.status === "running" ? "progress-track running" : "progress-track"}><i style={{ width: `${ratio * 100}%` }} /></div>
      <p>{progress?.message ?? "Sem processo em andamento."}</p>
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

function EmptyState({ text }: { text: string }) {
  return <div className="empty-state">{text}</div>;
}

ReactDOM.createRoot(document.getElementById("root")!).render(<App />);
