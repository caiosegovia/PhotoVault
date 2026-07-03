import logging
import queue
import shutil
import threading
from collections import Counter
from pathlib import Path
from tkinter import filedialog, ttk

import customtkinter as ctk

from core.patterns import preview_pattern, validate_pattern
from gui.components import ghost_button, page_frame, page_header, primary_button
from gui.theme import (
    ACCENT,
    ACCENT_HOVER,
    ACCENT_SOFT,
    BORDER,
    ERROR,
    FONT_FAMILY,
    FONT_SIZE_BODY,
    FONT_SIZE_HEADER,
    FONT_SIZE_SMALL,
    SUCCESS,
    SURFACE,
    SURFACE_ALT,
    SURFACE_MUTED,
    TEXT,
    TEXT_MUTED,
    TEXT_SUBTLE,
    WARNING,
)
from utils.formatting import format_count, format_size


log = logging.getLogger(__name__)


REASON_LABELS = {
    "new_asset": "Novo",
    "exact_duplicate_in_plan": "Duplicata na importacao",
    "exact_duplicate_in_vault": "Ja na galeria",
    "known_asset_in_vault": "Ja conhecido",
    "metadata_error": "Erro de leitura",
}


STATUS_LABELS = {
    "created": "Criada",
    "scanning": "Analisando",
    "analyzed": "Pronta",
    "running": "Importando",
    "completed": "Concluida",
    "failed": "Falhou",
    "cancelled": "Cancelada",
}


class OrganizeView:
    def __init__(self, parent, app, main_window):
        self.parent = parent
        self.app = app
        self.main_window = main_window
        self._queue: queue.Queue = queue.Queue()
        self._running = False
        self._imports: list[dict] = []
        self._selected_import_id: int | None = None
        self._files: list[dict] = []
        self.filter_var = ctk.StringVar(value="Todos")
        self.dest_var = ctk.StringVar(value=str(self.app.app_state.get("destination") or ""))
        self.pattern_var = ctk.StringVar(value=self.app.app_state.get("pattern", "{year}/{month:02d}"))
        self.mode_var = ctk.StringVar(value=self.app.app_state.get("mode", "copy"))
        self._build()

    def _build(self):
        self.scroll = page_frame(self.parent)
        header = page_header(
            self.scroll,
            "Galeria Permanente",
            "Importe pastas para uma galeria fixa. Cada importacao fica analisada, auditada e reaproveitavel.",
        )
        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.pack(side="right")
        ghost_button(actions, "Atualizar", self.refresh, width=110).pack(side="left", padx=(0, 8))
        primary_button(actions, "Nova importacao", self._choose_import_folder, width=165).pack(side="left")

        self._build_command_deck()
        self._build_overview()

        main = ctk.CTkFrame(self.scroll, fg_color="transparent")
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=5)
        main.columnconfigure(1, weight=4)

        left = ctk.CTkFrame(main, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        right = ctk.CTkFrame(main, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")

        detail_card = self._panel(left, "Console da importacao", "Revise o plano gerado e execute os arquivos novos.")
        self.detail_body = ctk.CTkFrame(detail_card, fg_color="transparent")
        self.detail_body.pack(fill="x", padx=12, pady=(0, 12))

        filters = ctk.CTkFrame(detail_card, fg_color="transparent")
        filters.pack(fill="x", padx=12, pady=(0, 10))
        ctk.CTkSegmentedButton(
            filters,
            values=["Todos", "Novos", "Duplicados", "Erros"],
            variable=self.filter_var,
            command=lambda _value: self._render_table(),
            height=32,
            fg_color=SURFACE_ALT,
            selected_color=ACCENT,
            selected_hover_color=ACCENT,
            unselected_color=SURFACE_ALT,
            unselected_hover_color=SURFACE_MUTED,
            text_color=TEXT,
            font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"),
        ).pack(side="left")
        self.execute_btn = primary_button(filters, "Importar novos", self._execute_selected, width=150, height=32)
        self.execute_btn.pack(side="right")

        self._build_table(detail_card)

        timeline_card = self._panel(right, "Ciclo de importacoes", "Historico e filas abertas da galeria.")
        self.timeline_body = ctk.CTkFrame(timeline_card, fg_color="transparent")
        self.timeline_body.pack(fill="x", padx=10, pady=(0, 12))

        charts_card = self._panel(right, "Storage e decisao", "Disco, status e impacto do lote selecionado.")
        self.charts_body = ctk.CTkFrame(charts_card, fg_color="transparent")
        self.charts_body.pack(fill="x", padx=12, pady=(0, 12))

        self.status_label = ctk.CTkLabel(
            self.scroll,
            text="",
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            text_color=TEXT_MUTED,
            anchor="w",
        )
        self.status_label.pack(fill="x", pady=(8, 0))

    def _build_command_deck(self):
        deck = ctk.CTkFrame(self.scroll, fg_color=SURFACE, corner_radius=8, border_width=1, border_color=BORDER)
        deck.pack(fill="x", pady=(0, 14))
        deck.columnconfigure(0, weight=3)
        deck.columnconfigure(1, weight=2)

        left = ctk.CTkFrame(deck, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=18, pady=18)
        ctk.CTkLabel(
            left,
            text="Importe. Revise. Persista.",
            font=(FONT_FAMILY, 28, "bold"),
            text_color=TEXT,
            anchor="w",
        ).pack(anchor="w")
        ctk.CTkLabel(
            left,
            text="A galeria e fixa; cada pasta vira uma importacao com diff, storage, status e historico.",
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            text_color=TEXT_MUTED,
            anchor="w",
            wraplength=720,
            justify="left",
        ).pack(anchor="w", pady=(4, 14))

        action_row = ctk.CTkFrame(left, fg_color="transparent")
        action_row.pack(fill="x")
        self.hero_new_btn = ctk.CTkButton(
            action_row,
            text="+ Nova importacao",
            command=self._choose_import_folder,
            width=190,
            height=48,
            corner_radius=8,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            text_color="#03110f",
            font=(FONT_FAMILY, 15, "bold"),
        )
        self.hero_new_btn.pack(side="left", padx=(0, 10))
        self.hero_import_btn = ctk.CTkButton(
            action_row,
            text="Importar selecionada",
            command=self._execute_selected,
            width=190,
            height=48,
            corner_radius=8,
            fg_color=SURFACE_ALT,
            hover_color=SURFACE_MUTED,
            border_width=1,
            border_color=BORDER,
            text_color=TEXT,
            font=(FONT_FAMILY, 14, "bold"),
        )
        self.hero_import_btn.pack(side="left")

        self.pipeline = ctk.CTkFrame(left, fg_color="transparent")
        self.pipeline.pack(fill="x", pady=(16, 0))

        right = ctk.CTkFrame(deck, fg_color=SURFACE_ALT, corner_radius=8, border_width=1, border_color=BORDER)
        right.grid(row=0, column=1, sticky="nsew", padx=(0, 18), pady=18)
        ctk.CTkLabel(right, text="Vault ativo", font=(FONT_FAMILY, FONT_SIZE_HEADER, "bold"), text_color=TEXT).pack(anchor="w", padx=14, pady=(12, 6))
        body = ctk.CTkFrame(right, fg_color="transparent")
        body.pack(fill="x", padx=14, pady=(0, 10))
        body.columnconfigure(0, weight=1)
        ctk.CTkEntry(
            body,
            textvariable=self.dest_var,
            height=38,
            fg_color=SURFACE_MUTED,
            border_color=BORDER,
            text_color=TEXT,
            placeholder_text="Pasta definitiva da galeria...",
            font=(FONT_FAMILY, FONT_SIZE_BODY),
        ).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ghost_button(body, "Pasta", self._browse_dest, width=80, height=38).grid(row=0, column=1)

        cfg = ctk.CTkFrame(right, fg_color="transparent")
        cfg.pack(fill="x", padx=14, pady=(0, 12))
        cfg.columnconfigure(1, weight=1)
        ctk.CTkLabel(cfg, text="Padrao", font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"), text_color=TEXT_MUTED).grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.pattern_entry = ctk.CTkEntry(
            cfg,
            textvariable=self.pattern_var,
            height=32,
            fg_color=SURFACE_ALT,
            border_color=BORDER,
            text_color=TEXT,
            font=(FONT_FAMILY, FONT_SIZE_SMALL),
        )
        self.pattern_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        ctk.CTkSegmentedButton(
            cfg,
            values=["copy", "move"],
            variable=self.mode_var,
            height=32,
            width=150,
            selected_color=ACCENT,
            selected_hover_color=ACCENT,
            unselected_color=SURFACE_ALT,
            unselected_hover_color=SURFACE_MUTED,
            font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"),
        ).grid(row=0, column=2)
        self.pattern_hint = ctk.CTkLabel(cfg, text="", font=(FONT_FAMILY, 10), text_color=TEXT_SUBTLE)
        self.pattern_hint.grid(row=1, column=1, sticky="w", pady=(4, 0))
        self.pattern_entry.bind("<KeyRelease>", lambda _event: self._update_pattern_hint())
        primary_button(right, "Salvar vault", self._save_vault, width=130, height=34).pack(anchor="e", padx=14, pady=(0, 12))

    def _build_overview(self):
        self.overview = ctk.CTkFrame(self.scroll, fg_color="transparent")
        self.overview.pack(fill="x", pady=(0, 14))

    def _build_table(self, parent):
        table_frame = ctk.CTkFrame(parent, fg_color="transparent")
        table_frame.pack(fill="both", expand=True, padx=10, pady=(0, 12))
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Imports.Treeview", background=SURFACE, foreground=TEXT, fieldbackground=SURFACE, borderwidth=0, rowheight=28, font=(FONT_FAMILY, FONT_SIZE_BODY))
        style.configure("Imports.Treeview.Heading", background=SURFACE_ALT, foreground=TEXT_MUTED, font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"))
        style.map("Imports.Treeview", background=[("selected", ACCENT)], foreground=[("selected", "#03110f")])
        self.tree = ttk.Treeview(
            table_frame,
            style="Imports.Treeview",
            columns=("status", "source", "gallery", "size", "decision"),
            show="headings",
            height=16,
        )
        for col, label, width in [
            ("status", "Status", 145),
            ("source", "Arquivo origem", 310),
            ("gallery", "Destino sugerido", 310),
            ("size", "Tamanho", 95),
            ("decision", "Decisao", 100),
        ]:
            self.tree.heading(col, text=label)
            self.tree.column(col, width=width, anchor="e" if col == "size" else "w")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda _event: self._open_selected_visual())
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")

    def refresh(self):
        self.dest_var.set(str(self.app.app_state.get("destination") or ""))
        self.pattern_var.set(self.app.app_state.get("pattern", "{year}/{month:02d}"))
        self.mode_var.set(self.app.app_state.get("mode", "copy"))
        self._update_pattern_hint()
        self._load_imports()
        self._render_all()

    def _load_imports(self):
        try:
            from core.database import get_import_files, list_imports

            self._imports = list_imports(80)
            valid_ids = {int(item["id"]) for item in self._imports}
            if self._selected_import_id not in valid_ids:
                self._selected_import_id = None
            if self._selected_import_id is None and self._imports:
                self._selected_import_id = int(self._imports[0]["id"])
            self._files = get_import_files(self._selected_import_id, limit=800) if self._selected_import_id else []
        except Exception:
            log.exception("failed to load imports")
            self._imports = []
            self._files = []

    def _render_all(self):
        self._render_pipeline()
        self._render_overview()
        self._render_timeline()
        self._render_charts()
        self._render_detail()
        self._render_table()
        self._sync_action_buttons()

    def _render_pipeline(self):
        self._clear(self.pipeline)
        selected = self._selected_import()
        stages = [
            ("Vault", bool(self.app.app_state.get("destination")), "destino fixo"),
            ("Analisar", bool(selected), "hash + metadata"),
            ("Decidir", bool(selected and selected.get("status") == "analyzed"), "novos vs duplicados"),
            ("Importar", bool(selected and selected.get("status") in {"running", "completed"}), "copia verificada"),
            ("Historico", bool(self._imports), "auditavel"),
        ]
        for idx, (title, active, subtitle) in enumerate(stages):
            cell = ctk.CTkFrame(self.pipeline, fg_color=ACCENT_SOFT if active else SURFACE_ALT, corner_radius=8)
            cell.pack(side="left", fill="x", expand=True, padx=(0 if idx == 0 else 5, 0 if idx == len(stages) - 1 else 5))
            ctk.CTkLabel(cell, text=title, font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"), text_color=ACCENT if active else TEXT_MUTED).pack(anchor="w", padx=10, pady=(8, 0))
            ctk.CTkLabel(cell, text=subtitle, font=(FONT_FAMILY, 10), text_color=TEXT_SUBTLE).pack(anchor="w", padx=10, pady=(0, 8))

    def _render_overview(self):
        self._clear(self.overview)
        for col in range(5):
            self.overview.columnconfigure(col, weight=1, uniform="overview")
        imports = self._imports
        completed = sum(1 for item in imports if item.get("status") == "completed")
        open_count = sum(1 for item in imports if item.get("status") in {"created", "scanning", "analyzed", "running"})
        imported = sum(item.get("files_imported") or 0 for item in imports)
        duplicates = sum(item.get("files_duplicate") or 0 for item in imports)
        bytes_imported = sum(item.get("bytes_imported") or 0 for item in imports)
        data = [
            ("Importacoes", format_count(len(imports)), f"{open_count} em aberto"),
            ("Concluidas", format_count(completed), "ciclo historico"),
            ("Arquivos na galeria", format_count(imported), "via importacoes"),
            ("Duplicatas evitadas", format_count(duplicates), "sem copiar"),
            ("Volume importado", format_size(bytes_imported), "persistido"),
        ]
        for idx, (title, value, subtitle) in enumerate(data):
            self._tile(self.overview, idx, title, value, subtitle)

    def _render_timeline(self):
        self._clear(self.timeline_body)
        if not self._imports:
            empty = ctk.CTkFrame(self.timeline_body, fg_color=SURFACE_ALT, corner_radius=8, border_width=1, border_color=BORDER)
            empty.pack(fill="x", pady=4)
            ctk.CTkLabel(empty, text="Sem importacoes", font=(FONT_FAMILY, FONT_SIZE_HEADER, "bold"), text_color=TEXT).pack(anchor="w", padx=14, pady=(14, 2))
            ctk.CTkLabel(empty, text="Clique em Nova importacao e escolha uma pasta para alimentar a galeria.", font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_MUTED, wraplength=380, justify="left").pack(anchor="w", padx=14, pady=(0, 12))
            primary_button(empty, "Nova importacao", self._choose_import_folder, width=150, height=34).pack(anchor="w", padx=14, pady=(0, 14))
            return
        for item in self._imports[:14]:
            selected = int(item["id"]) == self._selected_import_id
            status = item.get("status") or "created"
            row = ctk.CTkButton(
                self.timeline_body,
                text="",
                fg_color=ACCENT_SOFT if selected else SURFACE_ALT,
                hover_color=SURFACE_MUTED,
                corner_radius=8,
                height=76,
                command=lambda import_id=int(item["id"]): self._select_import(import_id),
            )
            row.pack(fill="x", pady=4)
            dot_color = self._status_color(status)
            ctk.CTkFrame(row, fg_color=dot_color, width=5, corner_radius=3).pack(side="left", fill="y", padx=(0, 10))
            text = ctk.CTkFrame(row, fg_color="transparent")
            text.pack(side="left", fill="both", expand=True, padx=(0, 8), pady=8)
            ctk.CTkLabel(text, text=item.get("name") or "Importacao", font=(FONT_FAMILY, FONT_SIZE_BODY, "bold"), text_color=TEXT, anchor="w").pack(anchor="w")
            created = str(item.get("created_at") or "")[:16].replace("T", " ")
            ctk.CTkLabel(text, text=f"{STATUS_LABELS.get(status, status)}  |  {created}", font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_MUTED, anchor="w").pack(anchor="w", pady=(2, 0))
            detail = f'{format_count(item.get("files_new") or 0)} novos  |  {format_count(item.get("files_duplicate") or 0)} duplicados  |  {format_size(item.get("bytes_new") or 0)}'
            ctk.CTkLabel(text, text=detail, font=(FONT_FAMILY, 10), text_color=TEXT_SUBTLE, anchor="w").pack(anchor="w", pady=(2, 0))

    def _render_charts(self):
        self._clear(self.charts_body)
        self._render_disk_chart()
        status_counts = Counter(item.get("status") or "created" for item in self._imports)
        self._bar_group(self.charts_body, "Status das importacoes", {STATUS_LABELS.get(k, k): v for k, v in status_counts.items()})
        selected = self._selected_import()
        if selected:
            self._bar_group(self.charts_body, "Composicao da importacao", {
                "Novos": selected.get("files_new") or 0,
                "Duplicados": selected.get("files_duplicate") or 0,
                "Erros": selected.get("files_error") or 0,
                "Importados": selected.get("files_imported") or 0,
            })

    def _render_disk_chart(self):
        dest = self.app.app_state.get("destination")
        box = ctk.CTkFrame(self.charts_body, fg_color=SURFACE_ALT, corner_radius=8, border_width=1, border_color=BORDER)
        box.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(box, text="Alocacao de disco", font=(FONT_FAMILY, FONT_SIZE_HEADER, "bold"), text_color=TEXT).pack(anchor="w", padx=12, pady=(10, 2))
        if not dest:
            ctk.CTkLabel(box, text="Defina o vault para ver capacidade.", font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_MUTED).pack(anchor="w", padx=12, pady=(0, 12))
            return
        try:
            usage = shutil.disk_usage(str(dest))
            selected = self._selected_import()
            pending = self._new_bytes(selected) if selected and selected.get("status") == "analyzed" else 0
            used_ratio = min(usage.used / usage.total, 1)
            pending_ratio = min(pending / usage.total, max(1 - used_ratio, 0))
            row = ctk.CTkFrame(box, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=(0, 8))
            ctk.CTkLabel(row, text=f"Usado {format_size(usage.used)}", font=(FONT_FAMILY, 10, "bold"), text_color=TEXT_MUTED).pack(side="left")
            ctk.CTkLabel(row, text=f"Livre {format_size(usage.free)}", font=(FONT_FAMILY, 10, "bold"), text_color=SUCCESS if pending <= usage.free else ERROR).pack(side="right")
            bar = ctk.CTkFrame(box, fg_color=SURFACE_MUTED, height=14, corner_radius=6)
            bar.pack(fill="x", padx=12, pady=(0, 8))
            ctk.CTkFrame(bar, fg_color="#64748b", corner_radius=6).place(relx=0, rely=0, relwidth=used_ratio, relheight=1)
            ctk.CTkFrame(bar, fg_color=ACCENT, corner_radius=6).place(relx=used_ratio, rely=0, relwidth=pending_ratio, relheight=1)
            if pending:
                msg = f"Importacao selecionada adiciona {format_size(pending)}."
                color = SUCCESS if pending <= usage.free else ERROR
            else:
                msg = "Selecione uma importacao pronta para ver impacto pendente."
                color = TEXT_MUTED
            ctk.CTkLabel(box, text=msg, font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"), text_color=color).pack(anchor="w", padx=12, pady=(0, 12))
        except Exception as exc:
            ctk.CTkLabel(box, text=f"Sem leitura de disco: {exc}", font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=WARNING).pack(anchor="w", padx=12, pady=(0, 12))

    def _render_detail(self):
        self._clear(self.detail_body)
        item = self._selected_import()
        if not item:
            self._empty(self.detail_body, "Selecione uma importacao na timeline.")
            return
        self._metric_row(self.detail_body, [
            ("Encontrados", format_count(item.get("files_found") or 0), format_size(item.get("bytes_found") or 0)),
            ("Novos", format_count(self._new_file_count(item)), format_size(self._new_bytes(item))),
            ("Duplicados", format_count(item.get("files_duplicate") or 0), "evitados"),
            ("Importados", format_count(item.get("files_imported") or 0), format_size(item.get("bytes_imported") or 0)),
        ])
        status = item.get("status") or "created"
        hint = ctk.CTkFrame(self.detail_body, fg_color=ACCENT_SOFT if status == "analyzed" else SURFACE_ALT, corner_radius=8)
        hint.pack(fill="x", pady=(10, 0))
        title, msg, color = self._decision_message(item)
        ctk.CTkLabel(hint, text=title, font=(FONT_FAMILY, FONT_SIZE_HEADER, "bold"), text_color=color).pack(anchor="w", padx=12, pady=(10, 2))
        ctk.CTkLabel(hint, text=msg, font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_MUTED, wraplength=720, justify="left").pack(anchor="w", padx=12, pady=(0, 10))

    def _render_table(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for idx, item in enumerate(self._filtered_files()):
            self.tree.insert(
                "",
                "end",
                iid=str(idx),
                values=(
                    REASON_LABELS.get(item.get("reason"), item.get("reason") or "Arquivo"),
                    item.get("src_path") or "",
                    item.get("dst_path") or "-",
                    format_size(item.get("size") or 0),
                    self._decision_label(item.get("decision")),
                ),
            )

    def _choose_import_folder(self):
        if not self._save_vault():
            return
        path = filedialog.askdirectory(title="Selecionar pasta para importar para a galeria")
        if path:
            self._start_import_analysis(Path(path))

    def _start_import_analysis(self, source_path: Path):
        if self._running:
            return
        self._running = True
        self.status_label.configure(text=f"Analisando importacao: {source_path}", text_color=TEXT_MUTED)

        def worker():
            try:
                from core.imports import create_import_analysis

                analysis = create_import_analysis(
                    source_path=source_path,
                    vault_root=Path(self.app.app_state["destination"]),
                    pattern=self.app.app_state.get("pattern", "{year}/{month:02d}"),
                    mode=self.app.app_state.get("mode", "copy"),
                    callback=lambda _path, done: self._queue.put(("progress", done)) if done == 1 or done % 25 == 0 else None,
                )
                self._queue.put(("done", analysis.import_id))
            except Exception as exc:
                log.exception("import analysis failed")
                self._queue.put(("error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()
        self._poll_queue()

    def _poll_queue(self):
        try:
            while True:
                event, payload = self._queue.get_nowait()
                if event == "progress":
                    self.status_label.configure(text=f"Analisando {format_count(payload)} arquivos...", text_color=TEXT_MUTED)
                elif event == "done":
                    self._running = False
                    self._selected_import_id = int(payload)
                    self.status_label.configure(text="Importacao analisada. Revise o impacto e importe os novos arquivos.", text_color=SUCCESS)
                    self.refresh()
                    return
                elif event == "error":
                    self._running = False
                    self.status_label.configure(text=f"Erro na importacao: {payload}", text_color=ERROR)
                    self.refresh()
                    return
        except queue.Empty:
            pass
        if self._running:
            self.parent.after(150, self._poll_queue)

    def _execute_selected(self):
        item = self._selected_import()
        if not item or not item.get("ingest_plan_id"):
            self.status_label.configure(text="Selecione uma importacao analisada antes de importar.", text_color=WARNING)
            return
        if not self._can_execute(item):
            self.status_label.configure(text="Esta importacao nao possui arquivos novos pendentes para importar.", text_color=WARNING)
            return
        from core.imports import load_import_analysis

        analysis = load_import_analysis(int(item["id"]))
        if not analysis:
            self.status_label.configure(text="Nao consegui carregar a importacao selecionada.", text_color=ERROR)
            return
        self.app.app_state["plan"] = analysis
        self.app.app_state["plan_kind"] = "ingest"
        self.app.app_state["ingest_plan_id"] = analysis.plan_id
        self.app.app_state["current_import_id"] = analysis.import_id
        self.main_window.navigate("progress")

    def _select_import(self, import_id: int):
        self._selected_import_id = import_id
        self._load_imports()
        self._render_all()

    def _selected_import(self):
        for item in self._imports:
            if int(item["id"]) == self._selected_import_id:
                return item
        return None

    def _filtered_files(self):
        selected = self.filter_var.get()
        if selected == "Novos":
            return [item for item in self._files if item.get("reason") == "new_asset"]
        if selected == "Duplicados":
            return [item for item in self._files if item.get("reason") in {"exact_duplicate_in_plan", "exact_duplicate_in_vault", "known_asset_in_vault"}]
        if selected == "Erros":
            return [item for item in self._files if item.get("status") == "error" or item.get("reason") == "metadata_error"]
        return self._files

    def _open_selected_visual(self):
        selection = self.tree.selection()
        if not selection:
            return
        try:
            item = self._filtered_files()[int(selection[0])]
        except Exception:
            return
        path = Path(item.get("src_path") or "")
        if not path.exists():
            self.status_label.configure(text="Arquivo nao encontrado para preview.", text_color=WARNING)
            return
        win = ctk.CTkToplevel(self.parent)
        win.title(path.name)
        win.geometry("740x620")
        win.configure(fg_color=SURFACE)
        from gui.widgets.thumbnail_viewer import ThumbnailViewer

        ThumbnailViewer(win, path, size=(680, 500)).pack(padx=20, pady=20)
        ctk.CTkLabel(win, text=str(path), font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_MUTED, wraplength=680).pack(padx=20)

    def _browse_dest(self):
        path = filedialog.askdirectory(title="Selecionar galeria PhotoVault")
        if path:
            self.dest_var.set(path)
            self._save_vault()

    def _save_vault(self):
        dest = self.dest_var.get().strip()
        pattern = self.pattern_var.get().strip()
        if not dest:
            self.status_label.configure(text="Escolha o diretorio fixo da galeria.", text_color=ERROR)
            return False
        if not validate_pattern(pattern):
            self.status_label.configure(text="Padrao de organizacao invalido.", text_color=ERROR)
            return False
        root = Path(dest)
        root.mkdir(parents=True, exist_ok=True)
        self.app.app_state["destination"] = root
        self.app.app_state["pattern"] = pattern
        self.app.app_state["mode"] = self.mode_var.get()
        self.status_label.configure(text="Vault salvo. Agora use Nova importacao para alimentar a galeria.", text_color=SUCCESS)
        self._render_charts()
        return True

    def _update_pattern_hint(self):
        pattern = self.pattern_var.get().strip()
        if validate_pattern(pattern):
            self.pattern_hint.configure(text=f"Exemplo: {preview_pattern(pattern)}", text_color=ACCENT)
        else:
            self.pattern_hint.configure(text="Padrao invalido.", text_color=ERROR)

    def _decision_message(self, item):
        status = item.get("status")
        new_count = self._new_file_count(item)
        if self._can_execute(item):
            return (
                "Pronta para importar",
                f"{format_count(new_count)} arquivos novos serao copiados; {format_count(item.get('files_duplicate') or 0)} duplicatas ficam fora.",
                SUCCESS,
            )
        if status == "completed":
            return ("Importacao concluida", "Os arquivos novos ja foram persistidos na galeria e registrados no historico.", SUCCESS)
        if status in {"scanning", "running"}:
            return ("Processo em andamento", "Acompanhe a execucao. Se o app fechar, o status fica registrado no banco.", WARNING)
        if status == "failed":
            return ("Importacao falhou", "Abra os erros no filtro para entender quais arquivos precisam de intervencao.", ERROR)
        return ("Sem novos arquivos", "Esta importacao nao possui itens novos para copiar neste momento.", TEXT_MUTED)

    def _new_file_count(self, item):
        count = item.get("files_new") or 0
        if count:
            return count
        return sum(1 for row in self._files if row.get("reason") == "new_asset" and row.get("decision") in {"copy", "move"})

    def _new_bytes(self, item):
        size = item.get("bytes_new") or 0
        if size:
            return size
        return sum((row.get("size") or 0) for row in self._files if row.get("reason") == "new_asset" and row.get("decision") in {"copy", "move"})

    def _can_execute(self, item=None):
        item = item or self._selected_import()
        if not item or not item.get("ingest_plan_id"):
            return False
        if item.get("status") in {"completed", "running", "scanning", "cancelled"}:
            return False
        return self._new_file_count(item) > 0

    def _sync_action_buttons(self):
        enabled = self._can_execute()
        state = "normal" if enabled else "disabled"
        try:
            self.execute_btn.configure(state=state)
            self.hero_import_btn.configure(
                state=state,
                fg_color=ACCENT if enabled else SURFACE_ALT,
                hover_color=ACCENT_HOVER if enabled else SURFACE_MUTED,
                text_color="#03110f" if enabled else TEXT_MUTED,
            )
        except Exception:
            pass

    def _status_color(self, status):
        if status == "completed":
            return SUCCESS
        if status in {"analyzed", "running", "scanning"}:
            return ACCENT
        if status == "failed":
            return ERROR
        return WARNING

    def _decision_label(self, decision):
        if decision == "skip":
            return "Ignorar"
        if decision == "move":
            return "Mover"
        if decision == "copy":
            return "Copiar"
        return decision or "-"

    def _tile(self, parent, col, title, value, subtitle):
        tile = ctk.CTkFrame(parent, fg_color=SURFACE, corner_radius=8, border_width=1, border_color=BORDER)
        tile.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 5, 0 if col == 4 else 5))
        ctk.CTkLabel(tile, text=title, font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_MUTED).pack(anchor="w", padx=12, pady=(10, 0))
        ctk.CTkLabel(tile, text=value, font=(FONT_FAMILY, 19, "bold"), text_color=TEXT).pack(anchor="w", padx=12)
        ctk.CTkLabel(tile, text=subtitle, font=(FONT_FAMILY, 10), text_color=TEXT_SUBTLE).pack(anchor="w", padx=12, pady=(0, 10))

    def _metric_row(self, parent, metrics):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x")
        for idx, (title, value, subtitle) in enumerate(metrics):
            tile = ctk.CTkFrame(row, fg_color=SURFACE_ALT, corner_radius=8, border_width=1, border_color=BORDER)
            tile.pack(side="left", fill="x", expand=True, padx=(0 if idx == 0 else 5, 0 if idx == len(metrics) - 1 else 5))
            ctk.CTkLabel(tile, text=title, font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_MUTED).pack(anchor="w", padx=12, pady=(9, 0))
            ctk.CTkLabel(tile, text=value, font=(FONT_FAMILY, 18, "bold"), text_color=TEXT).pack(anchor="w", padx=12)
            ctk.CTkLabel(tile, text=subtitle, font=(FONT_FAMILY, 10), text_color=TEXT_SUBTLE).pack(anchor="w", padx=12, pady=(0, 9))

    def _bar_group(self, parent, title, data):
        box = ctk.CTkFrame(parent, fg_color=SURFACE_ALT, corner_radius=8, border_width=1, border_color=BORDER)
        box.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(box, text=title, font=(FONT_FAMILY, FONT_SIZE_HEADER, "bold"), text_color=TEXT).pack(anchor="w", padx=12, pady=(10, 4))
        items = [(k, v) for k, v in data.items() if v]
        if not items:
            ctk.CTkLabel(box, text="Sem dados ainda.", font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_MUTED).pack(anchor="w", padx=12, pady=(0, 12))
            return
        max_value = max(value for _name, value in items) or 1
        for name, value in sorted(items, key=lambda kv: kv[1], reverse=True):
            row = ctk.CTkFrame(box, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=(2, 0))
            ctk.CTkLabel(row, text=str(name), font=(FONT_FAMILY, 10, "bold"), text_color=TEXT_MUTED).pack(side="left")
            ctk.CTkLabel(row, text=format_count(value), font=(FONT_FAMILY, 10, "bold"), text_color=TEXT).pack(side="right")
            bar = ctk.CTkFrame(box, fg_color=SURFACE_MUTED, corner_radius=4, height=7)
            bar.pack(fill="x", padx=12, pady=(1, 5))
            ctk.CTkFrame(bar, fg_color=ACCENT, corner_radius=4).place(relx=0, rely=0, relwidth=min(value / max_value, 1), relheight=1)

    def _panel(self, parent, title, subtitle):
        card = ctk.CTkFrame(parent, fg_color=SURFACE, corner_radius=8, border_width=1, border_color=BORDER)
        card.pack(fill="x", pady=(0, 14))
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=18, pady=(16, 10))
        ctk.CTkLabel(header, text=title, font=(FONT_FAMILY, FONT_SIZE_HEADER, "bold"), text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(header, text=subtitle, font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_MUTED).pack(anchor="w", pady=(3, 0))
        return card

    def _empty(self, parent, text):
        ctk.CTkLabel(parent, text=text, font=(FONT_FAMILY, FONT_SIZE_BODY), text_color=TEXT_MUTED).pack(anchor="w", padx=4, pady=14)

    def _clear(self, parent):
        for child in parent.winfo_children():
            child.destroy()
