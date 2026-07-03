import React from "react";
import ReactDOM from "react-dom/client";
import { invoke } from "@tauri-apps/api/core";
import {
  Archive,
  CheckCircle2,
  Clock3,
  Database,
  Eye,
  FileWarning,
  FolderInput,
  HardDrive,
  Images,
  Play,
  Save,
  SlidersHorizontal,
  Sparkles,
  RotateCcw,
  Trash2,
} from "lucide-react";
import "./styles.css";

type ImportStatus = "ready" | "done" | "running" | "failed";
type Decision = "import" | "skip" | "review";

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

type FileRow = {
  id: number;
  status: string;
  source: string;
  destination: string;
  size: string;
  sizeBytes: number;
  device: string;
  date: string;
  decision: Decision;
  reason: string;
};

type Vault = {
  id?: number;
  path: string;
  pattern: string;
};

type Disk = {
  total: number;
  used: number;
  free: number;
  pending: number;
};

type BackendState = {
  vault: Vault;
  imports: ImportItem[];
  files: FileRow[];
  disk: Disk;
  progress?: ProgressInfo;
  logPath?: string;
};

type ProgressInfo = {
  stage: string;
  message: string;
  current: number;
  total: number;
  path: string;
  status: string;
  updatedAt?: number;
  logPath?: string;
};

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
  return {
    ready: "Pronta",
    done: "Concluída",
    running: "Analisando",
    failed: "Falhou",
  }[status];
}

async function callBridge<T>(command: string, payload: unknown = {}) {
  return invoke<T>("bridge", { command, payload });
}

function App() {
  const [imports, setImports] = React.useState<ImportItem[]>([]);
  const [rows, setRows] = React.useState<FileRow[]>([]);
  const [vault, setVault] = React.useState<Vault>({ path: "", pattern: "{year}/{month:02d}" });
  const [disk, setDisk] = React.useState<Disk>({ total: 0, used: 0, free: 0, pending: 0 });
  const [selectedImportId, setSelectedImportId] = React.useState<number | null>(null);
  const [filter, setFilter] = React.useState("Todos");
  const [sourcePath, setSourcePath] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [message, setMessage] = React.useState("Carregando estado real do PhotoVault...");
  const [progress, setProgress] = React.useState<ProgressInfo | null>(null);
  const [logPath, setLogPath] = React.useState("");

  const selectedImport = imports.find((item) => item.id === selectedImportId) ?? imports[0];

  React.useEffect(() => {
    loadState();
  }, []);

  async function loadState(preferredImportId?: number) {
    try {
      const state = await callBridge<BackendState>("state");
      setVault(state.vault);
      setImports(state.imports);
      setRows(state.files);
      setDisk(state.disk);
      setProgress(state.progress ?? null);
      setLogPath(state.logPath ?? state.progress?.logPath ?? "");
      const nextId = preferredImportId ?? selectedImportId ?? state.imports[0]?.id ?? null;
      setSelectedImportId(nextId);
      setMessage(state.imports.length ? "Estado carregado do banco real." : "Configure o vault e crie a primeira importação.");
    } catch (error) {
      setMessage(`Erro ao carregar backend: ${String(error)}`);
    }
  }

  async function resetAll() {
    const confirmed = window.confirm("Resetar banco, histórico, logs e cache local do PhotoVault? A galeria física não será apagada.");
    if (!confirmed) return;
    setBusy(true);
    setMessage("Resetando ambiente local...");
    try {
      const state = await callBridge<BackendState>("reset_all");
      setVault(state.vault);
      setImports(state.imports);
      setRows(state.files);
      setDisk(state.disk);
      setSelectedImportId(null);
      setMessage("Ambiente resetado. Configure o vault e comece uma importação nova.");
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
    setMessage("Analisando importação. Para pastas grandes isso pode levar alguns minutos...");
    startProgressPolling();
    try {
      const result = await callBridge<{ importId: number }>("analyze_import", {
        sourcePath,
        vaultPath: vault.path,
        pattern: vault.pattern,
        mode: "copy",
      });
      await loadState(result.importId);
      setMessage("Importação analisada. Revise decisões antes de executar.");
    } catch (error) {
      setMessage(`Erro ao analisar importação: ${String(error)}`);
    } finally {
      setBusy(false);
      await refreshProgress();
    }
  }

  async function selectImport(item: ImportItem) {
    setSelectedImportId(item.id);
    setMessage(`Carregando arquivos de ${item.name}...`);
    try {
      const result = await callBridge<{ files: FileRow[] }>("files", { importId: item.id, limit: 1000 });
      setRows(result.files);
      setMessage("Importação carregada.");
    } catch (error) {
      setMessage(`Erro ao carregar arquivos: ${String(error)}`);
    }
  }

  const visibleRows = rows.filter((row) => {
    if (filter === "Novos") return row.status === "Novo";
    if (filter === "Duplicados") return row.status === "Duplicata";
    if (filter === "Revisão") return row.decision === "review";
    if (filter === "Erros") return row.status === "Erro";
    return true;
  });

  const counts = rows.reduce(
    (acc, row) => {
      acc[row.decision] += 1;
      return acc;
    },
    { import: 0, skip: 0, review: 0 } as Record<Decision, number>,
  );

  async function persistDecision(ids: number[], decision: Decision) {
    if (!ids.length) return;
    setBusy(true);
    setMessage("Persistindo decisões no plano...");
    try {
      await callBridge("update_decisions", { ids, decision });
      setRows((current) =>
        current.map((row) => (ids.includes(row.id) ? { ...row, decision } : row)),
      );
      setMessage("Decisões persistidas.");
    } catch (error) {
      setMessage(`Erro ao persistir decisões: ${String(error)}`);
    } finally {
      setBusy(false);
    }
  }

  function bulkDecision(decision: Decision) {
    persistDecision(visibleRows.map((row) => row.id), decision);
  }

  function rowDecision(rowId: number, decision: Decision) {
    persistDecision([rowId], decision);
  }

  async function executeSelected() {
    if (!selectedImport?.planId) {
      setMessage("Selecione uma importação com plano analisado.");
      return;
    }
    setBusy(true);
    setMessage("Executando importação aprovada...");
    startProgressPolling();
    try {
      await callBridge("execute_import", { planId: selectedImport.planId });
      await loadState(selectedImport.id);
      setMessage("Importação executada.");
    } catch (error) {
      setMessage(`Erro ao executar importação: ${String(error)}`);
    } finally {
      setBusy(false);
      await refreshProgress();
    }
  }

  async function refreshProgress() {
    try {
      const result = await callBridge<{ progress: ProgressInfo; logPath: string }>("progress");
      setProgress(result.progress);
      setLogPath(result.logPath || result.progress.logPath || "");
      if (result.progress.status === "running") {
        setMessage(result.progress.message);
      }
    } catch (error) {
      setMessage(`Erro ao ler progresso: ${String(error)}`);
    }
  }

  function startProgressPolling() {
    let ticks = 0;
    const timer = window.setInterval(async () => {
      ticks += 1;
      await refreshProgress();
      if (ticks > 720) {
        window.clearInterval(timer);
      }
    }, 1000);
    window.setTimeout(() => window.clearInterval(timer), 12 * 60 * 1000);
  }

  const importedTotal = imports.reduce((total, item) => total + item.fresh, 0);
  const duplicateTotal = imports.reduce((total, item) => total + item.duplicates, 0);
  const errorTotal = imports.reduce((total, item) => total + item.errors, 0);
  const usedPct = disk.total ? Math.min((disk.used / disk.total) * 100, 100) : 0;
  const pendingPct = disk.total ? Math.min((disk.pending / disk.total) * 100, 100 - usedPct) : 0;

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
          <button className="active"><Archive size={17} /> Galeria</button>
          <button><FolderInput size={17} /> Importações</button>
          <button><Images size={17} /> Explorar</button>
          <button><Database size={17} /> Auditoria</button>
        </nav>
        <div className="vault-chip">
          <span>Vault ativo</span>
          <strong>{vault.path || "não configurado"}</strong>
        </div>
      </aside>

      <section className="workspace">
        <header className="hero">
          <div>
            <p className="eyebrow"><Sparkles size={15} /> ciclo aberto de importações</p>
            <h1>Construa uma galeria confiável, uma importação por vez.</h1>
            <p className="hero-copy">
              Escolha uma pasta, valide duplicidades, ajuste decisões em massa e persista somente o plano aprovado.
            </p>
            <div className="path-grid">
              <input value={vault.path} onChange={(event) => setVault({ ...vault, path: event.target.value })} placeholder="Diretório fixo da galeria" />
              <input value={vault.pattern} onChange={(event) => setVault({ ...vault, pattern: event.target.value })} placeholder="Padrão: {year}/{month:02d}" />
              <button className="secondary small" onClick={saveVault} disabled={busy}><Save size={16} /> Salvar vault</button>
            </div>
            <div className="path-grid import">
              <input value={sourcePath} onChange={(event) => setSourcePath(event.target.value)} placeholder="Pasta de origem para nova importação" />
              <button className="primary" onClick={analyzeImport} disabled={busy}><FolderInput size={18} /> Nova importação</button>
              <button className="secondary" onClick={executeSelected} disabled={busy || !selectedImport?.planId}><Play size={18} /> Importar selecionada</button>
            </div>
            <div className="maintenance-actions">
              <button className="danger" onClick={resetAll} disabled={busy}><RotateCcw size={15} /> Resetar ambiente de teste</button>
            </div>
            <p className={`status-line ${busy ? "busy" : ""}`}>{message}</p>
            <ProgressPanel progress={progress} logPath={logPath} />
          </div>

          <section className="disk-panel">
            <div className="disk-top">
              <span><HardDrive size={15} /> Disco da galeria</span>
              <strong>{formatBytes(disk.free)} livres</strong>
            </div>
            <div className="capacity">
              <span style={{ width: `${usedPct}%` }} />
              <i style={{ left: `${usedPct}%`, width: `${pendingPct}%` }} />
            </div>
            <div className="legend">
              <span><b className="used" /> usado</span>
              <span><b className="pending" /> importação</span>
            </div>
            <div className="impact">
              <strong>{selectedImport?.bytes ?? "0 B"}</strong>
              <span>impacto da importação selecionada</span>
            </div>
          </section>
        </header>

        <section className="metrics">
          <Metric label="Importações" value={formatNumber(imports.length)} caption={`${imports.filter((item) => item.status !== "done").length} em aberto`} />
          <Metric label="Arquivos novos" value={formatNumber(importedTotal)} caption="planejados/importados" />
          <Metric label="Duplicatas evitadas" value={formatNumber(duplicateTotal)} caption="sem copiar" />
          <Metric label="Erros pendentes" value={formatNumber(errorTotal)} caption="revisão necessária" />
        </section>

        <section className="main-grid">
          <section className="console">
            <div className="section-head">
              <div>
                <p>Importação selecionada</p>
                <h2>{selectedImport?.name ?? "Nenhuma importação"}</h2>
              </div>
              {selectedImport ? <span className={`status ${selectedImport.status}`}>{statusLabel(selectedImport.status)}</span> : null}
            </div>

            <div className="decision-strip">
              <Metric label="Encontrados" value={formatNumber(selectedImport?.found ?? 0)} caption={selectedImport?.source ?? "-"} />
              <Metric label="Novos" value={formatNumber(selectedImport?.fresh ?? 0)} caption={selectedImport?.bytes ?? "0 B"} />
              <Metric label="Duplicados" value={formatNumber(selectedImport?.duplicates ?? 0)} caption="não entram" />
              <Metric label="Erros" value={formatNumber(selectedImport?.errors ?? 0)} caption="revisão" />
            </div>

            <section className="decision-panel">
              <div>
                <p>Sugestões e decisões</p>
                <h3>{counts.import} importar · {counts.skip} ignorar · {counts.review} revisar</h3>
              </div>
              <div className="bulk-actions">
                <button onClick={() => bulkDecision("import")} disabled={busy}><CheckCircle2 size={15} /> Importar filtrados</button>
                <button onClick={() => bulkDecision("skip")} disabled={busy}><Trash2 size={15} /> Ignorar filtrados</button>
                <button onClick={() => bulkDecision("review")} disabled={busy}><FileWarning size={15} /> Revisar filtrados</button>
              </div>
            </section>

            <div className="filters">
              {["Todos", "Novos", "Duplicados", "Revisão", "Erros"].map((item) => (
                <button
                  key={item}
                  className={filter === item ? "active" : ""}
                  onClick={() => setFilter(item)}
                >
                  {item}
                </button>
              ))}
            </div>

            <div className="file-table">
              <div className="row header">
                <span>Status</span><span>Origem</span><span>Destino</span><span>Decisão</span>
              </div>
              {visibleRows.map((row) => (
                <div className={`row ${row.status === "Novo" ? "good" : row.status === "Erro" ? "warn" : "muted"}`} key={row.id}>
                  <span>{row.status}</span>
                  <span>{row.source}<small>{row.device} · {row.date} · {row.size}</small></span>
                  <span>{row.destination}</span>
                  <select value={row.decision} onChange={(event) => rowDecision(row.id, event.target.value as Decision)} disabled={busy}>
                    <option value="import">Importar</option>
                    <option value="skip">Ignorar</option>
                    <option value="review">Revisar</option>
                  </select>
                </div>
              ))}
              {!visibleRows.length ? <div className="empty-row">Sem arquivos neste filtro.</div> : null}
            </div>
          </section>

          <aside className="timeline">
            <div className="section-head compact">
              <div>
                <p>Timeline</p>
                <h2>Importações</h2>
              </div>
              <Clock3 size={18} />
            </div>

            {imports.map((item) => (
              <button
                className={`import-card ${selectedImport?.id === item.id ? "active" : ""}`}
                key={item.id}
                onClick={() => selectImport(item)}
              >
                <span className={`status ${item.status}`}>{statusLabel(item.status)}</span>
                <strong>{item.name}</strong>
                <p>{formatNumber(item.fresh)} novos · {formatNumber(item.duplicates)} duplicados · {item.bytes}</p>
              </button>
            ))}
            {!imports.length ? <div className="empty-card">Nenhuma importação ainda.</div> : null}

            <div className="bars">
              <h3><SlidersHorizontal size={16} /> Status do plano</h3>
              <Bar label="Importar" value={rows.length ? Math.round((counts.import / rows.length) * 100) : 0} />
              <Bar label="Ignorar" value={rows.length ? Math.round((counts.skip / rows.length) * 100) : 0} />
              <Bar label="Revisão" value={rows.length ? Math.round((counts.review / rows.length) * 100) : 0} />
            </div>

            <div className="quick-card">
              <h3><Eye size={16} /> Próxima decisão</h3>
              <p>Filtre por revisão e trate vídeos grandes, erros e arquivos sem data antes de executar.</p>
            </div>
          </aside>
        </section>
      </section>
    </main>
  );
}

function Metric({ label, value, caption }: { label: string; value: string; caption: string }) {
  return (
    <article>
      <span>{label}</span>
      <strong>{value}</strong>
      <em>{caption}</em>
    </article>
  );
}

function Bar({ label, value }: { label: string; value: number }) {
  return (
    <>
      <label>{label} <span>{value}%</span></label>
      <div><span style={{ width: `${value}%` }} /></div>
    </>
  );
}

function ProgressPanel({ progress, logPath }: { progress: ProgressInfo | null; logPath: string }) {
  const current = progress?.current ?? 0;
  const total = progress?.total ?? 0;
  const ratio = total ? Math.min(current / total, 1) : progress?.status === "running" ? 0.18 : 0;
  return (
    <section className="progress-panel">
      <div>
        <span>Progresso</span>
        <strong>{progress?.message ?? "Sem processo em andamento."}</strong>
      </div>
      <div className="progress-track">
        <i style={{ width: `${ratio * 100}%` }} />
      </div>
      <p>
        {total ? `${formatNumber(current)} / ${formatNumber(total)}` : current ? `${formatNumber(current)} arquivos analisados` : "Aguardando processo"}
        {progress?.path ? ` · ${progress.path}` : ""}
      </p>
      <small>Log: {logPath || progress?.logPath || "será criado em .photovault/photovault.log"}</small>
    </section>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(<App />);
