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
import "./styles.css";

type ImportStatus = "ready" | "done" | "running" | "failed";
type Decision = "import" | "skip" | "review";
type View = "cockpit" | "gallery" | "import" | "reviews" | "logs";
type GalleryFilter = {
  media: string;
  year: string;
  month: string;
  extension: string;
  size: "all" | "large" | "small";
  query: string;
  problem: "all" | "missing-thumb" | "without-date" | "video" | "raw";
};

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

type Vault = { id?: number; path: string; pattern: string };
type Disk = { total: number; used: number; free: number; pending: number };

type GalleryItem = {
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
  qualityScore: number;
};

type Bucket = { label: string; count: number; bytes: string; bytesRaw: number };
type GalleryBreakdowns = { media: Bucket[]; years: Bucket[]; months: Bucket[]; extensions: Bucket[]; devices?: Bucket[]; cameras?: Bucket[] };
type GalleryState = {
  items: GalleryItem[];
  total: number;
  photos: number;
  videos: number;
  withoutDate: number;
  bytes: string;
  bytesTotal: number;
  breakdowns: GalleryBreakdowns;
  capabilities?: { ffmpegAvailable?: boolean };
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
  breakdowns: { media: [], years: [], months: [], extensions: [], devices: [], cameras: [] },
  capabilities: { ffmpegAvailable: false },
};
const EMPTY_IMPORT_INSIGHTS: ImportInsights = { reasonGroups: [], mediaGroups: [], statusGroups: [] };
const DEFAULT_FILTER: GalleryFilter = {
  media: "all",
  year: "all",
  month: "all",
  extension: "all",
  size: "all",
  query: "",
  problem: "all",
};

const RAW_EXTENSIONS = new Set(["cr2", "cr3", "nef", "arw", "dng", "raf", "rw2", "orf"]);
const VIDEO_TYPES = new Set(["video", "movie"]);
const PATTERN_PRESETS = [
  { label: "Ano / mes", value: "{year}/{month:02d}" },
  { label: "Ano / mes / tipo", value: "{year}/{month:02d}/{media_type}" },
  { label: "Ano / camera", value: "{year}/{camera_make}" },
  { label: "Ano / extensao", value: "{year}/{extension}" },
  { label: "Mes compacto", value: "{year}-{month:02d}" },
];

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

function statusLabel(status: ImportStatus) {
  return { ready: "Pronta", done: "Concluida", running: "Rodando", failed: "Falhou" }[status];
}

function decisionLabel(decision: Decision) {
  return { import: "Importar", skip: "Ignorar", review: "Revisar" }[decision];
}

function clean(value?: string) {
  return (value || "").trim();
}

function itemYear(item: GalleryItem) {
  const date = clean(item.date);
  return date && date !== "sem data" ? date.slice(0, 4) : "sem data";
}

function itemMonth(item: GalleryItem) {
  const date = clean(item.date);
  return date && date !== "sem data" ? date.slice(0, 7) : "sem data";
}

function isRaw(item: GalleryItem) {
  return RAW_EXTENSIONS.has(clean(item.extension).toLowerCase().replace(".", ""));
}

function isVideo(item: GalleryItem) {
  return VIDEO_TYPES.has(clean(item.mediaType).toLowerCase()) || ["mp4", "mov", "m4v", "avi"].includes(clean(item.extension).toLowerCase());
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
  const [vault, setVault] = React.useState<Vault>({ path: "", pattern: "{year}/{month:02d}" });
  const [disk, setDisk] = React.useState<Disk>({ total: 0, used: 0, free: 0, pending: 0 });
  const [selectedImportId, setSelectedImportId] = React.useState<number | null>(null);
  const [selectedGalleryId, setSelectedGalleryId] = React.useState<number | null>(null);
  const [sourcePath, setSourcePath] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [thumbsBusy, setThumbsBusy] = React.useState(false);
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
    const query = filter.query.trim().toLowerCase();
    return gallery.items.filter((item) => {
      const sizeBytes = Number(item.sizeBytes || 0);
      if (filter.media !== "all" && clean(item.mediaType).toLowerCase() !== filter.media.toLowerCase()) return false;
      if (filter.year !== "all" && itemYear(item) !== filter.year) return false;
      if (filter.month !== "all" && itemMonth(item) !== filter.month) return false;
      if (filter.extension !== "all" && clean(item.extension).toLowerCase() !== filter.extension.toLowerCase()) return false;
      if (filter.size === "large" && sizeBytes < 50 * 1024 * 1024) return false;
      if (filter.size === "small" && sizeBytes > 10 * 1024 * 1024) return false;
      if (filter.problem === "missing-thumb" && item.previewStatus === "ready") return false;
      if (filter.problem === "without-date" && itemYear(item) !== "sem data") return false;
      if (filter.problem === "video" && !isVideo(item)) return false;
      if (filter.problem === "raw" && !isRaw(item)) return false;
      if (query && !`${item.name} ${item.path} ${item.extension} ${item.date}`.toLowerCase().includes(query)) return false;
      return true;
    });
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
  const missingThumbCount = gallery.items.filter((item) => !item.thumbnail).length;
  const largeVideoBytes = gallery.items
    .filter((item) => isVideo(item) && Number(item.sizeBytes || 0) > 50 * 1024 * 1024)
    .reduce((sum, item) => sum + Number(item.sizeBytes || 0), 0);

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
      const result = await callBridge<GalleryState>("gallery", { limit: 120, ensureThumbnails: true });
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
      const result = await callBridge<GalleryState>("gallery", { limit: 160, ensureThumbnails });
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
      await callBridge("set_vault", { path: vault.path, pattern: vault.pattern });
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
    setBusy(true);
    setMessage("Executando importacao aprovada...");
    startProgressPolling();
    try {
      await callBridge("execute_import", { planId: selectedImport.planId, verifyMode: "size" });
      await loadState(selectedImport.id);
      setActiveView("gallery");
      setMessage("Importacao executada.");
    } catch (error) {
      setMessage(`Erro ao executar importacao: ${String(error)}`);
    } finally {
      setBusy(false);
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
    setFilter((current) => ({ ...current, ...next }));
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
          <strong>{vault.path || "nao configurado"}</strong>
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
            <h1>{headline(activeView, gallery, selectedImport)}</h1>
            <p>{message}</p>
          </div>
          <ProgressPanel progress={progress} />
        </header>

        {activeView === "cockpit" ? (
          <CockpitView
            gallery={gallery}
            imports={imports}
            selectedImport={selectedImport}
            duplicateTotal={duplicateTotal}
            importedTotal={importedTotal}
            errorTotal={errorTotal}
            importedBytesTotal={importedBytesTotal}
            rawCount={rawCount}
            missingThumbCount={missingThumbCount}
            largeVideoBytes={largeVideoBytes}
            onFilter={patchFilter}
            onView={setActiveView}
          />
        ) : null}

        {activeView === "gallery" ? (
          <GalleryView
            gallery={gallery}
            filter={filter}
            items={filteredItems}
            selectedItem={selectedGalleryItem}
            thumbsBusy={thumbsBusy}
            onFilter={patchFilter}
            onClear={() => setFilter(DEFAULT_FILTER)}
            onSelect={setSelectedGalleryId}
            onRefresh={() => refreshGallery(false)}
            onHydrate={() => refreshGallery(true)}
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
            canExecute={Boolean(selectedImport?.planId)}
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
          />
        ) : null}

        {activeView === "logs" ? <LogsView logs={logs} logPath={logPath} onRefresh={refreshLogs} /> : null}
      </section>
    </main>
  );
}

function headline(view: View, gallery: GalleryState, selectedImport: ImportItem | null) {
  if (view === "gallery") return `${formatNumber(gallery.total)} arquivos preservados`;
  if (view === "import") return "Nova importacao";
  if (view === "reviews") return selectedImport ? `Revisao de ${selectedImport.name}` : "Revisoes de importacao";
  if (view === "logs") return "Operacao e auditoria";
  return "Cockpit da galeria";
}

function CockpitView({
  gallery,
  imports,
  selectedImport,
  duplicateTotal,
  importedTotal,
  errorTotal,
  importedBytesTotal,
  rawCount,
  missingThumbCount,
  largeVideoBytes,
  onFilter,
  onView,
}: {
  gallery: GalleryState;
  imports: ImportItem[];
  selectedImport: ImportItem | null;
  duplicateTotal: number;
  importedTotal: number;
  errorTotal: number;
  importedBytesTotal: number;
  rawCount: number;
  missingThumbCount: number;
  largeVideoBytes: number;
  onFilter: (filter: Partial<GalleryFilter>) => void;
  onView: (view: View) => void;
}) {
  const videoShare = gallery.bytesTotal ? Math.round((gallery.breakdowns.media.find((item) => item.label === "video")?.bytesRaw ?? 0) / gallery.bytesTotal * 100) : 0;
  return (
    <div className="view-stack">
      <section className="overview">
        <Metric icon={Archive} label="Na galeria" value={formatNumber(gallery.total)} caption={gallery.bytes} />
        <Metric icon={Camera} label="Fotos" value={formatNumber(gallery.photos)} caption={`${formatNumber(gallery.withoutDate)} sem data`} />
        <Metric icon={Video} label="Videos" value={formatNumber(gallery.videos)} caption={formatBytes(largeVideoBytes)} />
        <Metric icon={CheckCircle2} label="Duplicatas evitadas" value={formatNumber(duplicateTotal)} caption={`${formatNumber(importedTotal)} novos`} />
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
          <SectionTitle eyebrow="Timeline" title="Meses com mais acervo" />
          <BarChart items={gallery.breakdowns.months} onPick={(label) => onFilter({ month: label })} />
        </div>

        <div className="panel span-2">
          <SectionTitle eyebrow="Espaco" title="Peso por extensao" />
          <BarChart items={gallery.breakdowns.extensions} mode="bytes" onPick={(label) => onFilter({ extension: label.toLowerCase() })} />
        </div>

        <div className="panel">
          <SectionTitle eyebrow="Origem tecnica" title="Dispositivos detectados" />
          <BarChart items={gallery.breakdowns.devices ?? []} onPick={() => onFilter({ problem: "all" })} />
        </div>

        <div className="panel">
          <SectionTitle eyebrow="Captura" title="Cameras catalogadas" />
          <FacetButtons items={gallery.breakdowns.cameras ?? []} onPick={() => onFilter({ problem: "all" })} />
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
        </div>
      </section>
    </div>
  );
}

function GalleryView({
  gallery,
  filter,
  items,
  selectedItem,
  thumbsBusy,
  onFilter,
  onClear,
  onSelect,
  onRefresh,
  onHydrate,
  onOpenPath,
  onRevealPath,
}: {
  gallery: GalleryState;
  filter: GalleryFilter;
  items: GalleryItem[];
  selectedItem: GalleryItem | null;
  thumbsBusy: boolean;
  onFilter: (filter: Partial<GalleryFilter>) => void;
  onClear: () => void;
  onSelect: (id: number) => void;
  onRefresh: () => void;
  onHydrate: () => void;
  onOpenPath: (path?: string) => void;
  onRevealPath: (path?: string) => void;
}) {
  const totalBytes = items.reduce((sum, item) => sum + Number(item.sizeBytes || 0), 0);
  return (
    <section className="gallery-layout">
      <aside className="filter-panel">
        <SectionTitle eyebrow="Filtros" title={`${formatNumber(items.length)} exibidos`} />
        <label className="search-box">
          <Search size={15} />
          <input value={filter.query} onChange={(event) => onFilter({ query: event.target.value })} placeholder="Buscar nome, pasta, data..." />
        </label>
        <FilterGroup title="Tipo">
          <Chip active={filter.media === "all"} onClick={() => onFilter({ media: "all" })}>Todos</Chip>
          {gallery.breakdowns.media.map((item) => <Chip key={item.label} active={filter.media === item.label} onClick={() => onFilter({ media: item.label })}>{item.label}</Chip>)}
        </FilterGroup>
        <FilterGroup title="Curadoria">
          <Chip active={filter.problem === "all"} onClick={() => onFilter({ problem: "all" })}>Todos</Chip>
          <Chip active={filter.problem === "missing-thumb"} onClick={() => onFilter({ problem: "missing-thumb" })}>Sem preview</Chip>
          <Chip active={filter.problem === "without-date"} onClick={() => onFilter({ problem: "without-date" })}>Sem data</Chip>
          <Chip active={filter.problem === "raw"} onClick={() => onFilter({ problem: "raw" })}>RAW</Chip>
          <Chip active={filter.problem === "video"} onClick={() => onFilter({ problem: "video" })}>Videos</Chip>
        </FilterGroup>
        <FilterGroup title="Ano">
          <Chip active={filter.year === "all"} onClick={() => onFilter({ year: "all" })}>Todos</Chip>
          {gallery.breakdowns.years.map((item) => <Chip key={item.label} active={filter.year === item.label} onClick={() => onFilter({ year: item.label })}>{item.label}</Chip>)}
        </FilterGroup>
        <FilterGroup title="Extensao">
          <Chip active={filter.extension === "all"} onClick={() => onFilter({ extension: "all" })}>Todas</Chip>
          {gallery.breakdowns.extensions.map((item) => <Chip key={item.label} active={filter.extension === item.label.toLowerCase()} onClick={() => onFilter({ extension: item.label.toLowerCase() })}>{item.label}</Chip>)}
        </FilterGroup>
        <FilterGroup title="Tamanho">
          <Chip active={filter.size === "all"} onClick={() => onFilter({ size: "all" })}>Todos</Chip>
          <Chip active={filter.size === "large"} onClick={() => onFilter({ size: "large" })}>Grandes</Chip>
          <Chip active={filter.size === "small"} onClick={() => onFilter({ size: "small" })}>Leves</Chip>
        </FilterGroup>
        <button className="ghost full" onClick={onClear}><Filter size={15} /> Limpar filtros</button>
      </aside>

      <div className="gallery-center">
        {!gallery.capabilities?.ffmpegAvailable ? (
          <div className="gallery-alert">
            <Film size={16} />
            <div>
              <strong>Frames de video indisponiveis</strong>
              <span>Instale as dependencias Python atualizadas para habilitar o extrator de frames. Fotos e RAW continuam com previews quando suportados.</span>
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
          </div>
        </div>
        <div className="month-strip">
          <button className={filter.month === "all" ? "active" : ""} onClick={() => onFilter({ month: "all" })}>
            <span>Todos</span><strong>{formatNumber(gallery.total)}</strong>
          </button>
          {gallery.breakdowns.months.map((item) => (
            <button key={item.label} className={filter.month === item.label ? "active" : ""} onClick={() => onFilter({ month: item.label })}>
              <span>{item.label}</span><strong>{formatNumber(item.count)}</strong>
            </button>
          ))}
        </div>
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
}) {
  return (
    <section className="import-layout">
      <div className="panel span-2">
        <SectionTitle eyebrow="Configuracao" title="Origem e vault" />
        <div className="form-grid">
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
          <div className="actions">
            <button className="secondary" onClick={() => onBulk("import")} disabled={busy}><CheckCircle2 size={15} /> Importar grupos</button>
            <button className="secondary" onClick={() => onBulk("skip")} disabled={busy}><Trash2 size={15} /> Ignorar grupos</button>
            <button className="secondary" onClick={() => onBulk("review")} disabled={busy}><FileWarning size={15} /> Revisar grupos</button>
            <button className="primary" onClick={onExecute} disabled={busy || !selectedImport?.planId}><Play size={15} /> Executar</button>
          </div>
          <DecisionCockpit groups={importInsights.reasonGroups} busy={busy} onDecision={onDecision} />
        </div>
      </div>
    </section>
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
    <button className="insight-card" onClick={onClick}>
      <Icon size={19} />
      <span>{title}</span>
      <strong>{value}</strong>
      <em>{detail}</em>
      <b>{action}</b>
    </button>
  );
}

function FacetButtons({ items, onPick }: { items: Bucket[]; onPick: (label: string) => void }) {
  const total = items.reduce((sum, item) => sum + item.count, 0);
  return (
    <div className="facet-buttons">
      {items.map((item) => {
        const pct = total ? Math.max(6, Math.round((item.count / total) * 100)) : 0;
        return (
          <button key={item.label} onClick={() => onPick(item.label)}>
            <div><strong>{item.label}</strong><span>{formatNumber(item.count)} | {item.bytes}</span></div>
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
          <button key={item.label} onClick={() => onPick(item.label)}>
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
