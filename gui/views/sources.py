import threading
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from gui.components import empty_state, ghost_button, page_frame, page_header, primary_button, section
from gui.theme import (
    ACCENT,
    APP_BG,
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
    WARNING,
)
from utils.formatting import format_count, format_size


class SourcesView:
    def __init__(self, parent, app, main_window):
        self.parent = parent
        self.app = app
        self.main_window = main_window
        self._scanning = False
        self._build()

    def _build(self):
        self.scroll = page_frame(self.parent)
        header = page_header(
            self.scroll,
            "Origens",
            "Adicione fontes candidatas. Nada sera copiado ate voce aprovar um plano.",
        )

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.pack(side="right")
        primary_button(actions, "Adicionar pasta", self._add_folder, width=150).pack(side="left", padx=(0, 8))
        ghost_button(actions, "Detectar drives", self._detect_drives, width=145).pack(side="left", padx=(0, 8))
        ghost_button(actions, "Google Photos", self._add_google_photos, width=135).pack(side="left")

        summary = ctk.CTkFrame(self.scroll, fg_color="transparent")
        summary.pack(fill="x", pady=(0, 14))
        for col in range(3):
            summary.columnconfigure(col, weight=1, uniform="summary")

        self.total_label = self._summary_tile(summary, 0, "Arquivos", "0")
        self.size_label = self._summary_tile(summary, 1, "Espaco", "0 B")
        self.sources_label = self._summary_tile(summary, 2, "Fontes", "0")

        insights_card = section(self.scroll, "Storage e inteligencia das origens", "Volume candidato, composicao e riscos antes da ingestao.")
        self.source_insights = ctk.CTkFrame(insights_card, fg_color="transparent")
        self.source_insights.pack(fill="x", padx=12, pady=(0, 12))

        list_card = section(self.scroll, "Origens adicionadas", "Estas fontes entram na comparacao textual contra a galeria.")
        self.sources_list = ctk.CTkFrame(list_card, fg_color="transparent")
        self.sources_list.pack(fill="x", padx=10, pady=(0, 10))

        bottom = ctk.CTkFrame(self.scroll, fg_color="transparent")
        bottom.pack(fill="x", pady=(2, 0))

        self.status_label = ctk.CTkLabel(
            bottom,
            text="",
            font=(FONT_FAMILY, FONT_SIZE_SMALL),
            text_color=TEXT_MUTED,
            anchor="w",
        )
        self.status_label.pack(side="left", fill="x", expand=True)

        self.scan_btn = primary_button(bottom, "Comparar origens", self._start_scan, width=170, height=42)
        self.scan_btn.pack(side="right")

        self.loading_bar = ctk.CTkProgressBar(
            self.scroll,
            mode="indeterminate",
            height=5,
            fg_color=SURFACE_ALT,
            progress_color=ACCENT,
        )

        self._refresh_sources()

    def _summary_tile(self, parent, col: int, title: str, value: str):
        tile = ctk.CTkFrame(parent, fg_color=SURFACE, corner_radius=8, border_width=1, border_color=BORDER)
        tile.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 8, 0 if col == 2 else 8))
        ctk.CTkLabel(
            tile,
            text=title,
            font=(FONT_FAMILY, FONT_SIZE_SMALL),
            text_color=TEXT_MUTED,
            anchor="w",
        ).pack(anchor="w", padx=16, pady=(14, 2))
        label = ctk.CTkLabel(
            tile,
            text=value,
            font=(FONT_FAMILY, 22, "bold"),
            text_color=TEXT,
            anchor="w",
        )
        label.pack(anchor="w", padx=16, pady=(0, 14))
        return label

    def _refresh_sources(self):
        for w in self.sources_list.winfo_children():
            w.destroy()

        sources = self.app.app_state.get("sources", [])
        total = sum(src.get("total", 0) for src in sources)
        size = sum(src.get("size_bytes", 0) for src in sources)
        self.total_label.configure(text=format_count(total))
        self.size_label.configure(text=format_size(size))
        self.sources_label.configure(text=format_count(len(sources)))
        self._render_source_insights(sources)

        if not sources:
            empty_state(self.sources_list, "Nenhuma fonte adicionada ainda.")
            return

        for src in sources:
            self._create_source_row(src)

    def _render_source_insights(self, sources: list[dict]):
        for child in self.source_insights.winfo_children():
            child.destroy()
        if not sources:
            empty_state(self.source_insights, "Adicione origens para ver graficos de storage.")
            return

        total_size = sum(src.get("size_bytes", 0) for src in sources)
        photos = sum(src.get("photos", 0) for src in sources)
        videos = sum(src.get("videos", 0) for src in sources)
        others = sum(src.get("others", 0) for src in sources)
        scanned = sum(1 for src in sources if src.get("status") in {"Escaneada", "Pronta para comparar"})

        row = ctk.CTkFrame(self.source_insights, fg_color="transparent")
        row.pack(fill="x")
        row.columnconfigure(0, weight=1)
        row.columnconfigure(1, weight=1)
        row.columnconfigure(2, weight=1)

        self._insight_tile(row, 0, "Volume candidato", format_size(total_size), "entrara na comparacao")
        self._insight_tile(row, 1, "Status", f"{scanned}/{len(sources)}", "origens prontas")
        self._insight_tile(row, 2, "Midia", f"{format_count(photos)} / {format_count(videos)}", "fotos / videos")

        chart_row = ctk.CTkFrame(self.source_insights, fg_color="transparent")
        chart_row.pack(fill="x", pady=(10, 0))
        chart_row.columnconfigure(0, weight=1)
        chart_row.columnconfigure(1, weight=2)

        type_box = self._chart_box(chart_row, 0, "Composicao")
        try:
            from gui.widgets.storage_chart import StorageDonutChart
            StorageDonutChart(type_box, {"Fotos": photos, "Videos": videos, "Outros": others}).pack(fill="both", expand=True, padx=6, pady=6)
        except Exception:
            self._bar_group(type_box, {"Fotos": photos, "Videos": videos, "Outros": others})

        by_source = {}
        for src in sources:
            label = Path(str(src.get("path", ""))).name or str(src.get("path", "Fonte"))
            by_source[label] = src.get("size_bytes", 0)
        self._bar_group(self._chart_box(chart_row, 1, "Volume por origem"), by_source, value_formatter=format_size)

        dest = self.app.app_state.get("destination")
        if dest:
            try:
                import shutil
                free = shutil.disk_usage(str(dest)).free
                if total_size > free:
                    msg = f"Atencao: origens somam {format_size(total_size - free)} acima do espaco livre do destino."
                    color = WARNING
                else:
                    msg = f"Espaco livre cobre o volume bruto das origens ({format_size(free)} livres)."
                    color = SUCCESS
                ctk.CTkLabel(self.source_insights, text=msg, font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"), text_color=color).pack(anchor="w", pady=(10, 0))
            except Exception:
                pass

    def _insight_tile(self, parent, col, title, value, subtitle):
        tile = ctk.CTkFrame(parent, fg_color=SURFACE_ALT, corner_radius=8)
        tile.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 6, 0))
        ctk.CTkLabel(tile, text=title, font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_MUTED).pack(anchor="w", padx=12, pady=(10, 0))
        ctk.CTkLabel(tile, text=value, font=(FONT_FAMILY, 18, "bold"), text_color=TEXT).pack(anchor="w", padx=12)
        ctk.CTkLabel(tile, text=subtitle, font=(FONT_FAMILY, 10), text_color=TEXT_MUTED).pack(anchor="w", padx=12, pady=(0, 10))

    def _chart_box(self, parent, col, title):
        box = ctk.CTkFrame(parent, fg_color=SURFACE_ALT, corner_radius=8, border_width=1, border_color=BORDER)
        box.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 8, 0))
        ctk.CTkLabel(box, text=title, font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"), text_color=TEXT).pack(anchor="w", padx=12, pady=(10, 4))
        return box

    def _bar_group(self, parent, data, value_formatter=None):
        items = [(k, v) for k, v in data.items() if v]
        if not items:
            ctk.CTkLabel(parent, text="Sem dados", font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_MUTED).pack(padx=12, pady=16)
            return
        items = sorted(items, key=lambda kv: kv[1], reverse=True)[:8]
        max_value = max(v for _k, v in items) or 1
        value_formatter = value_formatter or format_count
        for name, value in items:
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=(3, 0))
            ctk.CTkLabel(row, text=str(name), font=(FONT_FAMILY, 10), text_color=TEXT_MUTED, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=value_formatter(value), font=(FONT_FAMILY, 10, "bold"), text_color=TEXT).pack(side="right")
            bar = ctk.CTkFrame(parent, fg_color=SURFACE_MUTED, corner_radius=4, height=6)
            bar.pack(fill="x", padx=12, pady=(1, 5))
            ctk.CTkFrame(bar, fg_color=ACCENT, corner_radius=4).place(relx=0, rely=0, relwidth=min(value / max_value, 1), relheight=1)

    def _create_source_row(self, src: dict):
        row = ctk.CTkFrame(self.sources_list, fg_color=SURFACE_ALT, corner_radius=8)
        row.pack(fill="x", pady=4)

        left = ctk.CTkFrame(row, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True, padx=14, pady=12)

        src_type = src.get("type", "local")
        label = {"local": "Pasta", "drive": "Drive", "cloud": "Cloud"}.get(src_type, "Fonte")
        ctk.CTkLabel(
            left,
            text=label.upper(),
            font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"),
            text_color=ACCENT,
            anchor="w",
        ).pack(anchor="w")
        ctk.CTkLabel(
            left,
            text=str(src.get("path", "")),
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            text_color=TEXT,
            anchor="w",
            wraplength=780,
        ).pack(anchor="w", pady=(3, 0))

        status = src.get("status") or "Nao escaneada"
        details = f'{status}  |  {format_count(src.get("total", 0))} arquivos'
        if src.get("size_bytes"):
            details += f'  |  {format_size(src["size_bytes"])}'
        if src.get("last_scan"):
            details += f'  |  {src["last_scan"]}'
        ctk.CTkLabel(
            left,
            text=details,
            font=(FONT_FAMILY, FONT_SIZE_SMALL),
            text_color=TEXT_MUTED,
            anchor="w",
        ).pack(anchor="w", pady=(2, 0))

        ctk.CTkButton(
            row,
            text="Remover",
            width=90,
            height=30,
            fg_color="transparent",
            hover_color="#371b21",
            text_color=ERROR,
            border_width=1,
            border_color="#4a2229",
            corner_radius=8,
            font=(FONT_FAMILY, FONT_SIZE_SMALL),
            command=lambda s=src: self._remove_source(s),
        ).pack(side="right", padx=14)

    def _add_folder(self):
        path = filedialog.askdirectory(title="Selecionar pasta de fotos/videos")
        if path:
            self._count_and_add(Path(path), "local")

    def _count_and_add(self, path: Path, src_type: str):
        self.status_label.configure(text="Contando arquivos...")
        self.loading_bar.configure(mode="indeterminate")
        self.loading_bar.pack(fill="x", pady=(12, 0))
        self.loading_bar.start()

        def worker():
            from core.scanner import count_files

            counts = count_files(path)
            self.app.app_state["sources"].append({
                "path": str(path),
                "type": src_type,
                "status": "Pronta para comparar",
                "last_scan": None,
                **counts,
            })
            self.parent.after(0, self._on_source_added)

        threading.Thread(target=worker, daemon=True).start()

    def _on_source_added(self):
        self.loading_bar.stop()
        self.loading_bar.pack_forget()
        self.status_label.configure(text="")
        self._refresh_sources()

    def _remove_source(self, src: dict):
        self.app.app_state["sources"] = [
            s for s in self.app.app_state["sources"] if s["path"] != src["path"]
        ]
        self._refresh_sources()

    def _detect_drives(self):
        from core.scanner import detect_drives

        drives = detect_drives()
        if not drives:
            self.status_label.configure(text="Nenhum drive externo encontrado.")
            return
        self._show_drive_dialog(drives)

    def _show_drive_dialog(self, drives: list):
        win = ctk.CTkToplevel(self.parent)
        win.title("Selecionar drive")
        win.geometry("520x420")
        win.configure(fg_color=APP_BG)

        ctk.CTkLabel(
            win,
            text="Drives detectados",
            font=(FONT_FAMILY, FONT_SIZE_HEADER, "bold"),
            text_color=TEXT,
        ).pack(anchor="w", padx=20, pady=(20, 10))

        scroll = ctk.CTkScrollableFrame(win, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        for drive in drives:
            btn = ctk.CTkButton(
                scroll,
                text=f"{drive['label']}  |  {format_size(drive.get('total_space', 0))}",
                anchor="w",
                fg_color=SURFACE,
                hover_color=SURFACE_ALT,
                border_width=1,
                border_color=BORDER,
                corner_radius=8,
                height=44,
                font=(FONT_FAMILY, FONT_SIZE_BODY),
                command=lambda d=drive, w=win: self._select_drive(d, w),
            )
            btn.pack(fill="x", pady=4)

    def _select_drive(self, drive: dict, win):
        win.destroy()
        self._count_and_add(Path(drive["path"]), "drive")

    def _add_google_photos(self):
        try:
            from integrations.google_photos import GooglePhotosClient
            from utils.constants import CONFIG_DIR, TOKEN_PATH

            client = self.app.app_state.get("google_client")
            if client is None:
                creds_path = CONFIG_DIR / "google_client_secret.json"
                assets_path = Path("assets") / "google_client_secret.json"
                if not creds_path.exists() and assets_path.exists():
                    creds_path = assets_path
                if not creds_path.exists() and not TOKEN_PATH.exists():
                    self.status_label.configure(text="Configure as credenciais Google em Ajustes primeiro.")
                    return
                client = GooglePhotosClient(str(creds_path))

            if client.authenticate():
                self.app.app_state["google_client"] = client
                quota = client.get_storage_quota()
                self.app.app_state["sources"].append(
                    {
                        "path": "Google Photos",
                        "type": "cloud",
                        "status": "Conectada",
                        "last_scan": None,
                        "client": client,
                        "size_bytes": quota.get("used", 0),
                        "total": 0,
                    }
                )
                self._refresh_sources()
                self.status_label.configure(text="Google Photos conectado.")
            else:
                self.status_label.configure(text="Falha na autenticacao. Verifique os ajustes.")
        except Exception as e:
            self.status_label.configure(text=f"Erro: {e}")

    def _start_scan(self):
        sources = self.app.app_state.get("sources", [])
        if not sources:
            self.status_label.configure(text="Adicione ao menos uma origem antes de comparar.")
            return

        self._scanning = True
        self.scan_btn.configure(state="disabled", text="Escaneando...")
        self.status_label.configure(text="Escaneando origens...")
        self.loading_bar.configure(mode="determinate")
        self.loading_bar.set(0)
        self.loading_bar.pack(fill="x", pady=(12, 0))

        def worker():
            from core.scanner import count_files

            local_srcs = [s for s in sources if s.get("type") != "cloud"]
            n = len(local_srcs)
            totals = {"total": 0, "photos": 0, "videos": 0, "others": 0, "size_bytes": 0}
            for i, src in enumerate(local_srcs):
                src["status"] = "Escaneando"
                counts = count_files(Path(src["path"]))
                src.update(counts)
                src["status"] = "Escaneada"
                from datetime import datetime
                src["last_scan"] = datetime.now().strftime("%d/%m/%Y %H:%M")
                for k in totals:
                    totals[k] += counts.get(k, 0)
                val = (i + 1) / max(n, 1)
                idx = i + 1
                self.parent.after(
                    0,
                    lambda v=val, ix=idx, t=n: (
                        self.loading_bar.set(v),
                        self.status_label.configure(text=f"Pasta {ix} de {t}..."),
                    ),
                )
            self.app.app_state["scan_results"] = totals
            self.parent.after(0, self._on_scan_done)

        threading.Thread(target=worker, daemon=True).start()

    def _on_scan_done(self):
        self._scanning = False
        self.loading_bar.pack_forget()
        self.scan_btn.configure(state="normal", text="Comparar origens")
        results = self.app.app_state.get("scan_results", {})
        self.status_label.configure(
            text=f'Scan concluido: {format_count(results.get("total", 0))} arquivos encontrados.'
        )
        self.main_window.navigate("compare")

    def refresh(self):
        self._refresh_sources()
