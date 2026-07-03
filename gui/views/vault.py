import threading
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from core.patterns import BUILTIN_PATTERNS, preview_pattern, validate_pattern
from gui.components import ghost_button, page_frame, page_header, primary_button, section
from gui.theme import (
    ACCENT,
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


GALLERY_LIMIT = 72


class VaultView:
    def __init__(self, parent, app, main_window):
        self.parent = parent
        self.app = app
        self.main_window = main_window
        self._loading = False
        self._items = []
        self._summary = {}
        self._filter = ctk.StringVar(value="Todos")
        self._build()

    def _build(self):
        self.scroll = page_frame(self.parent)
        header = page_header(
            self.scroll,
            "Galeria",
            "Cockpit do Vault: saude, composicao, qualidade, historico e progresso de ingestao.",
        )
        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.pack(side="right")
        ghost_button(actions, "Atualizar", self.refresh, width=110).pack(side="left", padx=(0, 8))
        primary_button(actions, "Adicionar origens", lambda: self.main_window.navigate("sources"), width=160).pack(side="left")

        self._build_vault_selector()
        self._build_etl_timeline()
        self._build_metrics()
        self._build_storage_panel()
        self._build_filters()

        main = ctk.CTkFrame(self.scroll, fg_color="transparent")
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=3)
        main.columnconfigure(1, weight=2)

        left = ctk.CTkFrame(main, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        right = ctk.CTkFrame(main, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew")

        self.gallery_card = section(left, "Amostra visual", "Previews para consulta rapida. Use filtros para investigar.")
        self.gallery_body = ctk.CTkFrame(self.gallery_card, fg_color="transparent")
        self.gallery_body.pack(fill="x", padx=10, pady=(0, 12))

        self.insights_card = section(right, "Insights e sugestoes", "Prioridades geradas a partir da composicao atual.")
        self.insights_body = ctk.CTkFrame(self.insights_card, fg_color="transparent")
        self.insights_body.pack(fill="x", padx=12, pady=(0, 12))

        self.breakdown_card = section(right, "Composicao", "Agrupamentos clicaveis para orientar a curadoria.")
        self.breakdown_body = ctk.CTkFrame(self.breakdown_card, fg_color="transparent")
        self.breakdown_body.pack(fill="x", padx=12, pady=(0, 12))

        self.charts_card = section(self.scroll, "Graficos da galeria", "Distribuicao visual para enxergar volume, qualidade e origem rapidamente.")
        self.charts_body = ctk.CTkFrame(self.charts_card, fg_color="transparent")
        self.charts_body.pack(fill="x", padx=12, pady=(0, 12))

        self.history_card = section(self.scroll, "Historico recente", "Jobs executados e progresso acumulado.")
        self.history_body = ctk.CTkFrame(self.history_card, fg_color="transparent")
        self.history_body.pack(fill="x", padx=12, pady=(0, 12))

        self.status_label = ctk.CTkLabel(
            self.scroll,
            text="",
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            text_color=TEXT_MUTED,
            anchor="w",
        )
        self.status_label.pack(fill="x", pady=(4, 0))

    def _build_vault_selector(self):
        card = ctk.CTkFrame(self.scroll, fg_color=SURFACE, corner_radius=10, border_width=1, border_color=BORDER)
        card.pack(fill="x", pady=(0, 14))
        card.columnconfigure(0, weight=1)

        top = ctk.CTkFrame(card, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 8))
        top.columnconfigure(0, weight=1)
        ctk.CTkLabel(top, text="Vault ativo", font=(FONT_FAMILY, FONT_SIZE_HEADER, "bold"), text_color=TEXT).grid(row=0, column=0, sticky="w")

        body = ctk.CTkFrame(card, fg_color="transparent")
        body.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 16))
        body.columnconfigure(0, weight=1)
        self.dest_var = ctk.StringVar(value=str(self.app.app_state.get("destination") or ""))
        self.dest_entry = ctk.CTkEntry(
            body,
            textvariable=self.dest_var,
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            placeholder_text="Selecione a pasta da galeria definitiva...",
            height=40,
            fg_color=SURFACE_ALT,
            border_color=BORDER,
            text_color=TEXT,
        )
        self.dest_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ghost_button(body, "Escolher", self._browse_dest, width=105, height=40).grid(row=0, column=1, padx=(0, 8))
        primary_button(body, "Salvar", self._save_vault, width=95, height=40).grid(row=0, column=2)

        cfg = ctk.CTkFrame(card, fg_color="transparent")
        cfg.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 16))
        cfg.columnconfigure(1, weight=1)
        ctk.CTkLabel(cfg, text="Organizacao", font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_MUTED).grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.pattern_var = ctk.StringVar(value=self.app.app_state.get("pattern", "{year}/{month:02d}"))
        self.pattern_entry = ctk.CTkEntry(
            cfg,
            textvariable=self.pattern_var,
            font=(FONT_FAMILY, FONT_SIZE_SMALL),
            height=32,
            fg_color=SURFACE_ALT,
            border_color=BORDER,
            text_color=TEXT,
        )
        self.pattern_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        self.mode_var = ctk.StringVar(value=self.app.app_state.get("mode", "copy"))
        ctk.CTkSegmentedButton(
            cfg,
            values=["copy", "move"],
            variable=self.mode_var,
            font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"),
            selected_color=ACCENT,
            selected_hover_color=ACCENT,
            unselected_color=SURFACE_ALT,
            unselected_hover_color=SURFACE_MUTED,
            height=32,
            width=150,
        ).grid(row=0, column=2)
        self.pattern_hint = ctk.CTkLabel(cfg, text="", font=(FONT_FAMILY, 10), text_color=TEXT_SUBTLE)
        self.pattern_hint.grid(row=1, column=1, sticky="w", pady=(4, 0))
        self.pattern_entry.bind("<KeyRelease>", lambda _event: self._update_pattern_hint())
        self._update_pattern_hint()

    def _build_etl_timeline(self):
        card = ctk.CTkFrame(self.scroll, fg_color=SURFACE, corner_radius=10, border_width=1, border_color=BORDER)
        card.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(card, text="Timeline de organizacao", font=(FONT_FAMILY, FONT_SIZE_HEADER, "bold"), text_color=TEXT).pack(anchor="w", padx=18, pady=(14, 8))
        self.timeline = ctk.CTkFrame(card, fg_color="transparent")
        self.timeline.pack(fill="x", padx=18, pady=(0, 16))

    def _build_metrics(self):
        row = ctk.CTkFrame(self.scroll, fg_color="transparent")
        row.pack(fill="x", pady=(0, 14))
        for col in range(6):
            row.columnconfigure(col, weight=1, uniform="metrics")
        self.metric_labels = {}
        for idx, title in enumerate(["Itens", "Volume", "Fotos", "Videos", "Sem EXIF", "Plano"]):
            tile = ctk.CTkFrame(row, fg_color=SURFACE, corner_radius=8, border_width=1, border_color=BORDER)
            tile.grid(row=0, column=idx, sticky="ew", padx=(0 if idx == 0 else 5, 0 if idx == 5 else 5))
            ctk.CTkLabel(tile, text=title, font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_MUTED).pack(anchor="w", padx=12, pady=(10, 0))
            label = ctk.CTkLabel(tile, text="0", font=(FONT_FAMILY, 20, "bold"), text_color=TEXT)
            label.pack(anchor="w", padx=12, pady=(0, 10))
            self.metric_labels[title] = label

    def _build_storage_panel(self):
        self.storage_card = section(
            self.scroll,
            "Storage e capacidade",
            "Leitura do disco da galeria, volume atual e impacto estimado do plano aprovado.",
        )
        self.storage_body = ctk.CTkFrame(self.storage_card, fg_color="transparent")
        self.storage_body.pack(fill="x", padx=14, pady=(0, 14))

    def _build_filters(self):
        bar = ctk.CTkFrame(self.scroll, fg_color="transparent")
        bar.pack(fill="x", pady=(0, 12))
        ctk.CTkSegmentedButton(
            bar,
            values=["Todos", "Fotos", "Videos", "Sem EXIF", "Pesados", "Baixa res", "Sem data"],
            variable=self._filter,
            command=lambda _value: self._render_gallery(),
            fg_color=SURFACE,
            selected_color=ACCENT,
            selected_hover_color=ACCENT,
            unselected_color=SURFACE,
            unselected_hover_color=SURFACE_ALT,
            text_color=TEXT,
            font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"),
            height=34,
        ).pack(side="left")
        ghost_button(bar, "Comparar origens", lambda: self.main_window.navigate("compare"), width=150, height=34).pack(side="right")

    def _browse_dest(self):
        path = filedialog.askdirectory(title="Selecionar galeria PhotoVault")
        if path:
            self.dest_var.set(path)
            self._save_vault()

    def _update_pattern_hint(self):
        pat = self.pattern_var.get().strip()
        if validate_pattern(pat):
            self.pattern_hint.configure(text=f"Exemplo: {preview_pattern(pat)}", text_color=ACCENT)
        else:
            self.pattern_hint.configure(text="Padrao invalido.", text_color=ERROR)

    def _save_vault(self) -> bool:
        dest = self.dest_var.get().strip()
        pat = self.pattern_var.get().strip()
        if not dest:
            self.status_label.configure(text="Escolha uma pasta para a galeria.", text_color=ERROR)
            return False
        if not validate_pattern(pat):
            self.status_label.configure(text="Corrija o padrao de organizacao.", text_color=ERROR)
            return False
        path = Path(dest)
        path.mkdir(parents=True, exist_ok=True)
        self.app.app_state["destination"] = path
        self.app.app_state["pattern"] = pat
        self.app.app_state["mode"] = self.mode_var.get()
        self.status_label.configure(text="Vault salvo.", text_color=SUCCESS)
        self.refresh()
        return True

    def refresh(self):
        if self._loading:
            return
        destination = self.app.app_state.get("destination")
        if destination:
            self.dest_var.set(str(destination))
        self.pattern_var.set(self.app.app_state.get("pattern", "{year}/{month:02d}"))
        self.mode_var.set(self.app.app_state.get("mode", "copy"))
        self._update_pattern_hint()
        self._load_async()

    def _load_async(self):
        self._loading = True
        self.status_label.configure(text="Atualizando leitura da galeria...", text_color=TEXT_MUTED)

        def worker():
            items = self._collect_gallery_items()
            duplicate_paths = self._duplicate_paths()
            from core.gallery_insights import summarize_gallery

            summary = summarize_gallery(items, duplicate_paths)
            history = self._load_history()
            self.parent.after(0, lambda: self._render(items, summary, history))

        threading.Thread(target=worker, daemon=True).start()

    def _collect_gallery_items(self):
        destination = self.app.app_state.get("destination")
        if not destination:
            return []
        dest = Path(destination)
        if not dest.exists():
            return []
        sources = [{"path": dest, "label": "Galeria", "role": "destination", "type": "destination"}]
        items = []
        try:
            from core.database import query_gallery_records
            from core.gallery_insights import item_from_record

            records = query_gallery_records({"source_role": "destination"}, limit=GALLERY_LIMIT, offset=0)
            for record in records:
                item = item_from_record(record, sources)
                if item:
                    items.append(item)
            if items:
                return items
        except Exception:
            pass

        try:
            from core.gallery_insights import item_from_path
            from core.scanner import scan_directory

            for path in scan_directory(dest):
                item = item_from_path(path, sources)
                if item:
                    items.append(item)
                if len(items) >= GALLERY_LIMIT:
                    break
        except Exception:
            pass
        return items

    def _load_history(self):
        try:
            from core.database import get_scan_history

            return [dict(row) for row in get_scan_history(6)]
        except Exception:
            return []

    def _render(self, items, summary, history):
        self._loading = False
        self._items = items
        self._summary = summary
        self._render_timeline(history)
        self._render_metrics()
        self._render_storage()
        self._render_gallery()
        self._render_insights()
        self._render_breakdowns()
        self._render_charts()
        self._render_history(history)
        self.status_label.configure(text=f"Galeria atualizada: {format_count(len(items))} itens na amostra.", text_color=TEXT_MUTED)

    def _render_timeline(self, history):
        self._clear(self.timeline)
        steps = [
            ("Vault", bool(self.app.app_state.get("destination")), "galeria definida"),
            ("Origens", bool(self.app.app_state.get("sources")), "fontes candidatas"),
            ("Comparar", bool(self.app.app_state.get("plan")), "diff gerado"),
            ("Executar", bool(history), "jobs registrados"),
            ("Auditar", bool(history and history[0].get("status") == "completed"), "ultima execucao"),
        ]
        for idx, (title, active, subtitle) in enumerate(steps):
            cell = ctk.CTkFrame(self.timeline, fg_color=ACCENT_SOFT if active else SURFACE_ALT, corner_radius=8)
            cell.pack(side="left", fill="x", expand=True, padx=(0 if idx == 0 else 6, 0 if idx == len(steps) - 1 else 6))
            ctk.CTkLabel(cell, text=f"{idx + 1}. {title}", font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"), text_color=ACCENT if active else TEXT_MUTED).pack(anchor="w", padx=10, pady=(8, 0))
            ctk.CTkLabel(cell, text=subtitle, font=(FONT_FAMILY, 10), text_color=TEXT_MUTED).pack(anchor="w", padx=10, pady=(0, 8))

    def _render_metrics(self):
        total_size = sum(item.size for item in self._items)
        self.metric_labels["Itens"].configure(text=format_count(len(self._items)))
        self.metric_labels["Volume"].configure(text=format_size(total_size))
        self.metric_labels["Fotos"].configure(text=format_count(self._summary.get("photos", 0)))
        self.metric_labels["Videos"].configure(text=format_count(self._summary.get("videos", 0)))
        self.metric_labels["Sem EXIF"].configure(text=format_count(self._summary.get("missing_exif", 0)))
        plan = self.app.app_state.get("plan")
        self.metric_labels["Plano"].configure(text=format_count(len(plan.operations)) if plan else "0")

    def _render_storage(self):
        self._clear(self.storage_body)
        destination = self.app.app_state.get("destination")
        if not destination:
            self._empty(self.storage_body, "Defina a galeria para ver capacidade e storage.")
            return

        used_by_gallery = sum(item.size for item in self._items)
        plan = self.app.app_state.get("plan")
        plan_new_bytes = 0
        plan_new_count = 0
        if plan:
            for op in plan.operations:
                if isinstance(op, dict) and op.get("action") != "skip":
                    plan_new_bytes += op.get("size") or 0
                    plan_new_count += 1

        try:
            import shutil

            usage = shutil.disk_usage(str(destination))
            total = usage.total
            used = usage.used
            free = usage.free
        except Exception:
            total = used = free = 0

        row = ctk.CTkFrame(self.storage_body, fg_color="transparent")
        row.pack(fill="x")
        data = [
            ("Disco", format_size(total), "capacidade total"),
            ("Livre", format_size(free), "antes da ingestao"),
            ("Galeria", format_size(used_by_gallery), "amostra/catalogo"),
            ("Plano novo", format_size(plan_new_bytes), f"{format_count(plan_new_count)} itens"),
        ]
        for idx, (title, value, subtitle) in enumerate(data):
            tile = ctk.CTkFrame(row, fg_color=SURFACE_ALT, corner_radius=8)
            tile.pack(side="left", fill="x", expand=True, padx=(0 if idx == 0 else 5, 0 if idx == len(data) - 1 else 5))
            ctk.CTkLabel(tile, text=title, font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_MUTED).pack(anchor="w", padx=12, pady=(10, 0))
            ctk.CTkLabel(tile, text=value, font=(FONT_FAMILY, 18, "bold"), text_color=TEXT).pack(anchor="w", padx=12)
            ctk.CTkLabel(tile, text=subtitle, font=(FONT_FAMILY, 10), text_color=TEXT_SUBTLE).pack(anchor="w", padx=12, pady=(0, 10))

        if total > 0:
            bar = ctk.CTkFrame(self.storage_body, fg_color=SURFACE_MUTED, corner_radius=5, height=12)
            bar.pack(fill="x", pady=(12, 4))
            used_ratio = min(used / total, 1)
            add_ratio = min(plan_new_bytes / total, max(1 - used_ratio, 0))
            ctk.CTkFrame(bar, fg_color="#64748b", corner_radius=5).place(relx=0, rely=0, relwidth=used_ratio, relheight=1)
            ctk.CTkFrame(bar, fg_color=ACCENT, corner_radius=5).place(relx=used_ratio, rely=0, relwidth=add_ratio, relheight=1)
            if plan_new_bytes > free:
                msg = f"Atencao: o plano excede o espaco livre em {format_size(plan_new_bytes - free)}."
                color = WARNING
            elif plan_new_bytes and plan_new_bytes > free * 0.75:
                msg = "Plano cabe, mas vai consumir boa parte do espaco livre."
                color = WARNING
            elif plan_new_bytes:
                msg = "Plano cabe no disco atual com folga."
                color = SUCCESS
            else:
                msg = "Sem plano aprovado ainda; compare origens para estimar impacto."
                color = TEXT_MUTED
            ctk.CTkLabel(self.storage_body, text=msg, font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"), text_color=color).pack(anchor="w")

    def _render_gallery(self):
        self._clear(self.gallery_body)
        items = self._filtered_items()
        if not items:
            self._empty(self.gallery_body, "Nenhum item neste filtro. Defina a galeria ou execute uma ingestao.")
            return
        grid = ctk.CTkFrame(self.gallery_body, fg_color="transparent")
        grid.pack(fill="x")
        for col in range(4):
            grid.columnconfigure(col, weight=1, uniform="gallery")
        for idx, item in enumerate(items[:32]):
            self._preview_card(grid, item, idx)

    def _preview_card(self, parent, item, idx):
        card = ctk.CTkFrame(parent, fg_color=SURFACE_ALT, corner_radius=8, border_width=1, border_color=BORDER)
        card.grid(row=idx // 4, column=idx % 4, sticky="nsew", padx=6, pady=6)
        from gui.widgets.thumbnail_viewer import ThumbnailViewer

        ThumbnailViewer(card, item.path, size=(190, 122)).pack(fill="x", padx=8, pady=(8, 5))
        ctk.CTkLabel(card, text=item.name, font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"), text_color=TEXT, wraplength=190, anchor="w").pack(anchor="w", padx=9)
        meta = f"{item.year} | {item.resolution_label} | {format_size(item.size)}"
        ctk.CTkLabel(card, text=meta, font=(FONT_FAMILY, 10), text_color=TEXT_MUTED, wraplength=190).pack(anchor="w", padx=9)
        chips = ctk.CTkFrame(card, fg_color="transparent")
        chips.pack(fill="x", padx=8, pady=(5, 8))
        for chip in item.chips[:4]:
            self._pill(chips, chip, command=lambda c=chip: self._set_filter_from_chip(c))

    def _render_insights(self):
        self._clear(self.insights_body)
        actions = self._summary.get("actions", [])
        if not actions:
            self._empty(self.insights_body, "Sem sugestoes ainda.")
            return
        for title, text in actions[:5]:
            row = ctk.CTkFrame(self.insights_body, fg_color=ACCENT_SOFT, corner_radius=8)
            row.pack(fill="x", pady=4)
            ctk.CTkLabel(row, text=title, font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"), text_color=ACCENT).pack(anchor="w", padx=10, pady=(8, 1))
            ctk.CTkLabel(row, text=text, font=(FONT_FAMILY, 10), text_color=TEXT_MUTED, wraplength=360, justify="left").pack(anchor="w", padx=10, pady=(0, 8))

    def _render_breakdowns(self):
        self._clear(self.breakdown_body)
        self._rank_group("Qualidade", self._summary.get("quality", {}), self._quality_filter)
        self._rank_group("Dispositivos", self._summary.get("devices", {}), None)
        self._rank_group("Datas", self._summary.get("date_groups", {}), None)
        self._rank_group("Anos", self._summary.get("years", {}), None)

    def _render_charts(self):
        self._clear(self.charts_body)
        if not self._items:
            self._empty(self.charts_body, "Sem dados para graficos ainda.")
            return

        row = ctk.CTkFrame(self.charts_body, fg_color="transparent")
        row.pack(fill="x")
        row.columnconfigure(0, weight=1)
        row.columnconfigure(1, weight=1)
        row.columnconfigure(2, weight=1)

        type_box = self._chart_box(row, 0, "Tipos")
        try:
            from gui.widgets.storage_chart import StorageDonutChart

            StorageDonutChart(
                type_box,
                {
                    "Fotos": self._summary.get("photos", 0),
                    "Videos": self._summary.get("videos", 0),
                    "Alertas": self._summary.get("missing_exif", 0) + self._summary.get("low_resolution", 0),
                },
            ).pack(fill="both", expand=True, padx=6, pady=6)
        except Exception:
            self._mini_bar_group(type_box, {
                "Fotos": self._summary.get("photos", 0),
                "Videos": self._summary.get("videos", 0),
                "Alertas": self._summary.get("missing_exif", 0) + self._summary.get("low_resolution", 0),
            })

        self._mini_bar_group(self._chart_box(row, 1, "Qualidade"), self._summary.get("quality", {}), limit=7)
        self._mini_bar_group(self._chart_box(row, 2, "Anos"), self._summary.get("years", {}), limit=7)

        row2 = ctk.CTkFrame(self.charts_body, fg_color="transparent")
        row2.pack(fill="x", pady=(10, 0))
        row2.columnconfigure(0, weight=1)
        row2.columnconfigure(1, weight=1)
        self._mini_bar_group(self._chart_box(row2, 0, "Dispositivos"), self._summary.get("devices", {}), limit=8)
        self._mini_bar_group(self._chart_box(row2, 1, "Meses"), self._summary.get("date_groups", {}), limit=8)

    def _chart_box(self, parent, col, title):
        box = ctk.CTkFrame(parent, fg_color=SURFACE_ALT, corner_radius=8, border_width=1, border_color=BORDER)
        box.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 6, 0))
        ctk.CTkLabel(box, text=title, font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"), text_color=TEXT).pack(anchor="w", padx=12, pady=(10, 4))
        return box

    def _mini_bar_group(self, parent, data, limit=6):
        if not data:
            ctk.CTkLabel(parent, text="Sem dados", font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_MUTED).pack(padx=12, pady=16)
            return
        items = sorted(data.items(), key=lambda kv: kv[1], reverse=True)[:limit]
        max_count = max(count for _name, count in items) or 1
        for name, count in items:
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=(3, 0))
            ctk.CTkLabel(row, text=str(name), font=(FONT_FAMILY, 10), text_color=TEXT_MUTED, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=format_count(count), font=(FONT_FAMILY, 10, "bold"), text_color=TEXT).pack(side="right")
            bar = ctk.CTkFrame(parent, fg_color=SURFACE_MUTED, corner_radius=4, height=6)
            bar.pack(fill="x", padx=12, pady=(1, 5))
            ctk.CTkFrame(bar, fg_color=ACCENT, corner_radius=4).place(relx=0, rely=0, relwidth=min(count / max_count, 1), relheight=1)

    def _rank_group(self, title, data, mapper):
        if not data:
            return
        ctk.CTkLabel(self.breakdown_body, text=title, font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"), text_color=TEXT).pack(anchor="w", padx=4, pady=(10, 4))
        max_count = max(data.values()) or 1
        for name, count in sorted(data.items(), key=lambda kv: kv[1], reverse=True)[:7]:
            row = ctk.CTkButton(
                self.breakdown_body,
                text=f"{name}   {format_count(count)}",
                anchor="w",
                height=28,
                fg_color="transparent",
                hover_color=SURFACE_ALT,
                text_color=TEXT_MUTED,
                font=(FONT_FAMILY, 10, "bold"),
                command=lambda n=name, m=mapper: self._apply_group_filter(n, m),
            )
            row.pack(fill="x", pady=1)
            bar = ctk.CTkFrame(self.breakdown_body, fg_color=SURFACE_MUTED, corner_radius=4, height=4)
            bar.pack(fill="x", pady=(0, 3))
            ctk.CTkFrame(bar, fg_color=ACCENT, corner_radius=4).place(relx=0, rely=0, relwidth=min(count / max_count, 1), relheight=1)

    def _render_history(self, history):
        self._clear(self.history_body)
        if not history:
            self._empty(self.history_body, "Nenhum job executado ainda.")
            return
        for job in history:
            row = ctk.CTkFrame(self.history_body, fg_color=SURFACE_ALT, corner_radius=8)
            row.pack(fill="x", pady=4)
            status = job.get("status") or "completed"
            started = job.get("started_at") or "-"
            processed = job.get("files_processed") or 0
            errors = job.get("errors") or 0
            ctk.CTkLabel(row, text=status.upper(), width=95, font=(FONT_FAMILY, 10, "bold"), text_color=SUCCESS if status == "completed" else WARNING).pack(side="left", padx=10, pady=9)
            ctk.CTkLabel(row, text=str(started)[:16], font=(FONT_FAMILY, 10), text_color=TEXT_MUTED).pack(side="left", padx=8)
            ctk.CTkLabel(row, text=f"{format_count(processed)} processados", font=(FONT_FAMILY, 10), text_color=TEXT).pack(side="left", padx=8)
            ctk.CTkLabel(row, text=f"{errors} erros", font=(FONT_FAMILY, 10), text_color=ERROR if errors else TEXT_MUTED).pack(side="right", padx=10)

    def _filtered_items(self):
        selected = self._filter.get()
        if selected == "Fotos":
            return [item for item in self._items if item.media_type == "photo"]
        if selected == "Videos":
            return [item for item in self._items if item.media_type == "video"]
        if selected == "Sem EXIF":
            return [item for item in self._items if not item.has_exif]
        if selected == "Pesados":
            return [item for item in self._items if item.size >= 50 * 1024 * 1024]
        if selected == "Baixa res":
            return [item for item in self._items if "Baixa resolucao" in item.flags]
        if selected == "Sem data":
            return [item for item in self._items if not item.date_taken]
        return self._items

    def _set_filter_from_chip(self, chip):
        mapped = self._quality_filter(chip)
        if mapped:
            self._filter.set(mapped)
            self._render_gallery()

    def _apply_group_filter(self, name, mapper):
        if mapper:
            mapped = mapper(name)
            if mapped:
                self._filter.set(mapped)
                self._render_gallery()

    def _quality_filter(self, value):
        if value in {"Sem EXIF"}:
            return "Sem EXIF"
        if value in {"Pesado", "Muito pesado"}:
            return "Pesados"
        if value in {"Baixa res", "Baixa resolucao"}:
            return "Baixa res"
        if value in {"Video"}:
            return "Videos"
        return None

    def _duplicate_paths(self):
        dup = self.app.app_state.get("dup_result")
        paths = set()
        if not dup:
            return paths
        for group in list(dup.exact.values()) + list(dup.visual.values()):
            for path in group:
                paths.add(str(path))
        return paths

    def _pill(self, parent, text, command=None):
        btn = ctk.CTkButton(
            parent,
            text=text,
            width=max(56, len(text) * 7),
            height=20,
            corner_radius=6,
            fg_color=ACCENT_SOFT,
            hover_color=SURFACE_MUTED,
            text_color=ACCENT,
            font=(FONT_FAMILY, 9, "bold"),
            command=command,
        )
        btn.pack(side="left", padx=(0, 4), pady=2)

    def _empty(self, parent, text):
        ctk.CTkLabel(parent, text=text, font=(FONT_FAMILY, FONT_SIZE_BODY), text_color=TEXT_MUTED).pack(pady=18)

    def _clear(self, parent):
        for child in parent.winfo_children():
            child.destroy()
