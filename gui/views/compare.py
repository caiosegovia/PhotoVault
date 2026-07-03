import threading
import logging
import queue
from pathlib import Path
from tkinter import ttk

import customtkinter as ctk

from gui.components import ghost_button, page_frame, page_header, primary_button, section
from gui.theme import (
    ACCENT,
    BORDER,
    ERROR,
    FONT_FAMILY,
    FONT_SIZE_BODY,
    FONT_SIZE_SMALL,
    SUCCESS,
    SURFACE,
    SURFACE_ALT,
    TEXT,
    TEXT_MUTED,
    WARNING,
)
from utils.formatting import format_count, format_size


REASON_LABELS = {
    "new_asset": "Novo",
    "exact_duplicate_in_plan": "Duplicata na origem",
    "exact_duplicate_in_vault": "Ja na galeria",
    "already_in_vault": "No vault",
    "known_asset_in_vault": "Ja conhecido",
}


log = logging.getLogger(__name__)


class CompareView:
    def __init__(self, parent, app, main_window):
        self.parent = parent
        self.app = app
        self.main_window = main_window
        self._running = False
        self._ops: list[dict] = []
        self._queue: queue.Queue = queue.Queue()
        self.filter_var = ctk.StringVar(value="Todos")
        self._build()

    def _build(self):
        self.scroll = page_frame(self.parent)
        header = page_header(
            self.scroll,
            "Comparar",
            "Diff textual entre origens candidatas e a galeria. Imagem so quando voce pedir.",
        )
        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.pack(side="right")
        ghost_button(actions, "Atualizar", self._build_comparison, width=110).pack(side="left", padx=(0, 8))
        primary_button(actions, "Comparar agora", self._build_comparison, width=150).pack(side="left")

        metrics = ctk.CTkFrame(self.scroll, fg_color="transparent")
        metrics.pack(fill="x", pady=(0, 14))
        for col in range(5):
            metrics.columnconfigure(col, weight=1, uniform="compare_metrics")
        self.metric_labels = {}
        for idx, key in enumerate(["Novos", "Duplicatas", "Galeria", "Revisao", "Volume novo"]):
            tile = ctk.CTkFrame(metrics, fg_color=SURFACE, corner_radius=8, border_width=1, border_color=BORDER)
            tile.grid(row=0, column=idx, sticky="ew", padx=(0 if idx == 0 else 6, 0 if idx == 4 else 6))
            ctk.CTkLabel(tile, text=key, font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_MUTED).pack(anchor="w", padx=12, pady=(10, 0))
            label = ctk.CTkLabel(tile, text="0", font=(FONT_FAMILY, 20, "bold"), text_color=TEXT)
            label.pack(anchor="w", padx=12, pady=(0, 10))
            self.metric_labels[key] = label

        filter_row = ctk.CTkFrame(self.scroll, fg_color="transparent")
        filter_row.pack(fill="x", pady=(0, 10))
        self.filter = ctk.CTkSegmentedButton(
            filter_row,
            values=["Todos", "Novos", "Duplicatas", "Galeria", "Revisao"],
            variable=self.filter_var,
            command=lambda _value: self._render_table(),
            fg_color=SURFACE,
            selected_color=ACCENT,
            selected_hover_color=ACCENT,
            unselected_color=SURFACE,
            unselected_hover_color=SURFACE_ALT,
            text_color=TEXT,
            font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"),
            height=34,
        )
        self.filter.pack(side="left")

        table_card = section(self.scroll, "Resultado textual", "Clique duas vezes em uma linha para ver detalhes e abrir referencia visual.")
        table_frame = ctk.CTkFrame(table_card, fg_color="transparent")
        table_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Compare.Treeview", background=SURFACE, foreground=TEXT, fieldbackground=SURFACE, borderwidth=0, font=(FONT_FAMILY, FONT_SIZE_BODY))
        style.configure("Compare.Treeview.Heading", background=SURFACE_ALT, foreground=TEXT_MUTED, font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"))
        style.map("Compare.Treeview", background=[("selected", ACCENT)])

        self.tree = ttk.Treeview(
            table_frame,
            style="Compare.Treeview",
            columns=("status", "source", "gallery", "size", "action"),
            show="headings",
            height=18,
        )
        self.tree.heading("status", text="Status")
        self.tree.heading("source", text="Origem")
        self.tree.heading("gallery", text="Galeria")
        self.tree.heading("size", text="Tamanho")
        self.tree.heading("action", text="Acao sugerida")
        self.tree.column("status", width=140)
        self.tree.column("source", width=330)
        self.tree.column("gallery", width=330)
        self.tree.column("size", width=100, anchor="e")
        self.tree.column("action", width=140)
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda _event: self._open_selected_details())
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")

        self.status_label = ctk.CTkLabel(
            self.scroll,
            text="",
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            text_color=TEXT_MUTED,
            anchor="w",
        )
        self.status_label.pack(fill="x", pady=(8, 12))

        nav = ctk.CTkFrame(self.scroll, fg_color="transparent")
        nav.pack(fill="x")
        ghost_button(nav, "Voltar para Origens", lambda: self.main_window.navigate("sources"), width=170, height=42).pack(side="left")
        primary_button(nav, "Aprovar plano", self._approve_plan, width=160, height=42).pack(side="right")

    def _build_comparison(self):
        if self._running:
            return
        destination = self.app.app_state.get("destination")
        sources = [s for s in self.app.app_state.get("sources", []) if s.get("type") != "cloud"]
        if not destination:
            self.status_label.configure(text="Defina a galeria antes de comparar.", text_color=ERROR)
            return
        if not sources:
            self.status_label.configure(text="Adicione ao menos uma origem.", text_color=ERROR)
            return

        log.info("compare start destination=%s sources=%s", destination, [s.get("path") for s in sources])
        self._running = True
        self._queue = queue.Queue()
        self.status_label.configure(text="Comparando por SHA-256 e montando diff textual...", text_color=TEXT_MUTED)
        self._clear_tree()
        self._poll_queue()

        def worker():
            try:
                from core.ingestion import build_ingest_plan

                plan = build_ingest_plan(
                    sources=[Path(s["path"]) for s in sources],
                    vault_root=Path(destination),
                    pattern=self.app.app_state.get("pattern", "{year}/{month:02d}"),
                    mode=self.app.app_state.get("mode", "copy"),
                    callback=lambda _path, done: self._progress(done),
                )
                log.info("compare done plan_id=%s ops=%s", plan.plan_id, len(plan.operations))
                self._queue.put(("done", plan))
            except Exception as exc:
                log.exception("compare failed")
                self._queue.put(("error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _progress(self, done: int):
        if done == 1 or done % 10 == 0:
            log.info("compare progress files=%s", done)
            self._queue.put(("progress", done))

    def _poll_queue(self):
        try:
            while True:
                event, payload = self._queue.get_nowait()
                if event == "progress":
                    self.status_label.configure(text=f"Comparando {format_count(payload)} arquivos...")
                elif event == "done":
                    plan = payload
                    self.app.app_state["plan"] = plan
                    self.app.app_state["plan_kind"] = "ingest"
                    self.app.app_state["ingest_plan_id"] = plan.plan_id
                    self._ops = plan.operations
                    self._comparison_done()
                    return
                elif event == "error":
                    self._comparison_error(payload)
                    return
        except queue.Empty:
            pass
        if self._running:
            self.parent.after(150, self._poll_queue)

    def _comparison_done(self):
        self._running = False
        self._render_metrics()
        self._render_table()
        self.status_label.configure(text="Comparacao pronta. Revise o diff e aprove o plano.", text_color=SUCCESS)

    def _comparison_error(self, msg: str):
        self._running = False
        self.status_label.configure(text=f"Erro na comparacao: {msg}", text_color=ERROR)

    def _render_metrics(self):
        new_ops = [op for op in self._ops if op.get("reason") == "new_asset"]
        dup_ops = [op for op in self._ops if op.get("reason") in {"exact_duplicate_in_plan", "exact_duplicate_in_vault", "known_asset_in_vault"}]
        vault_ops = [op for op in self._ops if op.get("reason") == "already_in_vault"]
        review_ops = [op for op in self._ops if op.get("reason") not in REASON_LABELS]
        new_size = sum(op.get("size") or 0 for op in new_ops)
        self.metric_labels["Novos"].configure(text=format_count(len(new_ops)))
        self.metric_labels["Duplicatas"].configure(text=format_count(len(dup_ops)))
        self.metric_labels["Galeria"].configure(text=format_count(len(vault_ops)))
        self.metric_labels["Revisao"].configure(text=format_count(len(review_ops)))
        self.metric_labels["Volume novo"].configure(text=format_size(new_size))

    def _render_table(self):
        self._clear_tree()
        for idx, op in enumerate(self._filtered_ops()):
            reason = op.get("reason", "")
            status = REASON_LABELS.get(reason, "Revisao")
            src = Path(op.get("src_path", ""))
            dst = Path(op.get("dst_path", ""))
            action = self._action_label(op)
            gallery = str(dst)
            if reason in {"exact_duplicate_in_plan"}:
                gallery = "-"
            self.tree.insert(
                "",
                "end",
                iid=str(idx),
                values=(status, str(src), gallery, format_size(op.get("size") or 0), action),
            )

    def _filtered_ops(self) -> list[dict]:
        selected = self.filter_var.get()
        if selected == "Novos":
            return [op for op in self._ops if op.get("reason") == "new_asset"]
        if selected == "Duplicatas":
            return [op for op in self._ops if op.get("reason") in {"exact_duplicate_in_plan", "exact_duplicate_in_vault", "known_asset_in_vault"}]
        if selected == "Galeria":
            return [op for op in self._ops if op.get("reason") == "already_in_vault"]
        if selected == "Revisao":
            return [op for op in self._ops if op.get("reason") not in REASON_LABELS]
        return self._ops

    def _action_label(self, op: dict) -> str:
        if op.get("action") == "skip":
            return "Ignorar"
        if op.get("action") == "move":
            return "Mover"
        return "Ingerir"

    def _open_selected_details(self):
        selection = self.tree.selection()
        if not selection:
            return
        filtered = self._filtered_ops()
        try:
            op = filtered[int(selection[0])]
        except Exception:
            return
        self._open_details(op)

    def _open_details(self, op: dict):
        win = ctk.CTkToplevel(self.parent)
        win.title("Detalhes da comparacao")
        win.geometry("760x420")
        win.configure(fg_color=SURFACE)
        win.transient(self.parent.winfo_toplevel())

        body = ctk.CTkFrame(win, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=20)
        reason = op.get("reason", "")
        ctk.CTkLabel(body, text=REASON_LABELS.get(reason, "Revisao"), font=(FONT_FAMILY, 22, "bold"), text_color=TEXT).pack(anchor="w")
        details = [
            ("Origem", op.get("src_path", "")),
            ("Destino sugerido", op.get("dst_path", "")),
            ("Acao", self._action_label(op)),
            ("Motivo tecnico", reason),
            ("SHA-256", op.get("sha256", "")),
            ("Tamanho", format_size(op.get("size") or 0)),
        ]
        for label, value in details:
            row = ctk.CTkFrame(body, fg_color=SURFACE_ALT, corner_radius=8)
            row.pack(fill="x", pady=4)
            ctk.CTkLabel(row, text=label, width=130, anchor="w", font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"), text_color=TEXT_MUTED).pack(side="left", padx=10, pady=8)
            ctk.CTkLabel(row, text=str(value), anchor="w", font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT, wraplength=560).pack(side="left", fill="x", expand=True, padx=10, pady=8)

        buttons = ctk.CTkFrame(body, fg_color="transparent")
        buttons.pack(fill="x", pady=(12, 0))
        ghost_button(buttons, "Ver referencia visual", lambda: self._open_visual(op), width=170).pack(side="left")
        primary_button(buttons, "Fechar", win.destroy, width=100).pack(side="right")

    def _open_visual(self, op: dict):
        path = Path(op.get("src_path", ""))
        if not path.exists():
            self.status_label.configure(text="Arquivo de origem nao encontrado para preview visual.", text_color=WARNING)
            return
        win = ctk.CTkToplevel(self.parent)
        win.title(path.name)
        win.geometry("720x620")
        win.configure(fg_color=SURFACE)
        from gui.widgets.thumbnail_viewer import ThumbnailViewer

        viewer = ThumbnailViewer(win, path, size=(660, 500))
        viewer.pack(padx=20, pady=20)
        ctk.CTkLabel(win, text=str(path), font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_MUTED, wraplength=660).pack(padx=20)

    def _approve_plan(self):
        if not self.app.app_state.get("plan"):
            self._build_comparison()
            return
        self.main_window.navigate("progress")

    def _clear_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

    def refresh(self):
        plan = self.app.app_state.get("plan")
        if plan and self.app.app_state.get("plan_kind") == "ingest":
            self._ops = plan.operations
            self._render_metrics()
            self._render_table()
