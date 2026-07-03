import threading
from pathlib import Path

import customtkinter as ctk

from core.gallery_insights import GalleryItem, item_from_path, item_from_record, summarize_gallery
from gui.components import empty_state, ghost_button, page_frame, page_header, primary_button
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
    SURFACE,
    SURFACE_ALT,
    SURFACE_MUTED,
    TEXT,
    TEXT_MUTED,
    TEXT_SUBTLE,
    WARNING,
)
from gui.widgets.thumbnail_viewer import ThumbnailViewer
from utils.formatting import format_count, format_size


GALLERY_LIMIT = 120
GRID_COLUMNS = 5


class InventoryView:
    def __init__(self, parent, app, main_window):
        self.parent = parent
        self.app = app
        self.main_window = main_window
        self._loading_gallery = False
        self._indexing = False
        self._gallery_gen = 0
        self._items: list[GalleryItem] = []
        self._summary: dict = {}
        self.filter_var = ctk.StringVar(value="Todos")
        self.date_filter_var = ctk.StringVar(value="Qualquer data")
        self.origin_filter_var = ctk.StringVar(value="Qualquer origem")
        self.quality_filter_var = ctk.StringVar(value="Qualquer qualidade")
        self._build()

    def _build(self):
        self.scroll = page_frame(self.parent)
        header = page_header(
            self.scroll,
            "Inventario visual",
            "Galeria inteligente para decidir o que revisar, apagar, preservar e organizar.",
        )
        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.pack(side="right")
        ghost_button(actions, "Atualizar", self.refresh, width=110).pack(side="left", padx=(0, 8))
        ghost_button(actions, "Indexar", self._index_sources, width=110).pack(side="left", padx=(0, 8))
        primary_button(actions, "Duplicatas", lambda: self.main_window.navigate("duplicates"), width=130).pack(side="left")

        self.hero = ctk.CTkFrame(self.scroll, fg_color=SURFACE, corner_radius=8, border_width=1, border_color=BORDER)
        self.hero.pack(fill="x", pady=(0, 14))
        self.hero.columnconfigure(0, weight=3)
        self.hero.columnconfigure(1, weight=2)

        left = ctk.CTkFrame(self.hero, fg_color="transparent")
        left.grid(row=0, column=0, sticky="nsew", padx=20, pady=18)
        ctk.CTkLabel(
            left,
            text="Biblioteca em leitura",
            font=(FONT_FAMILY, 28, "bold"),
            text_color=TEXT,
            anchor="w",
        ).pack(anchor="w")
        self.hero_status = ctk.CTkLabel(
            left,
            text="Carregando inventario...",
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            text_color=TEXT_MUTED,
            anchor="w",
            wraplength=720,
        )
        self.hero_status.pack(anchor="w", pady=(6, 14))

        self.metrics = ctk.CTkFrame(left, fg_color="transparent")
        self.metrics.pack(fill="x")
        for col in range(4):
            self.metrics.columnconfigure(col, weight=1, uniform="metrics")
        self.total_files_lbl = self._metric(0, "Itens", "0", "na amostra")
        self.total_size_lbl = self._metric(1, "Volume", "0 B", "estimado")
        self.device_count_lbl = self._metric(2, "Origens", "0", "aparelhos/apps")
        self.issue_count_lbl = self._metric(3, "Alertas", "0", "para curadoria")

        right = ctk.CTkFrame(self.hero, fg_color=SURFACE_ALT, corner_radius=8)
        right.grid(row=0, column=1, sticky="nsew", padx=(0, 18), pady=18)
        ctk.CTkLabel(
            right,
            text="Prioridades sugeridas",
            font=(FONT_FAMILY, FONT_SIZE_HEADER, "bold"),
            text_color=TEXT,
        ).pack(anchor="w", padx=16, pady=(14, 6))
        self.actions_body = ctk.CTkFrame(right, fg_color="transparent")
        self.actions_body.pack(fill="x", padx=12, pady=(0, 12))

        self.filter_bar = ctk.CTkFrame(self.scroll, fg_color="transparent")
        self.filter_bar.pack(fill="x", pady=(0, 12))
        self.filter = ctk.CTkSegmentedButton(
            self.filter_bar,
            values=["Todos", "Fotos", "Videos", "Sem EXIF", "Pesados", "Problemas"],
            variable=self.filter_var,
            command=lambda _value: self._load_gallery_async(force=True),
            fg_color=SURFACE,
            selected_color=ACCENT,
            selected_hover_color=ACCENT_HOVER,
            unselected_color=SURFACE,
            unselected_hover_color=SURFACE_ALT,
            text_color=TEXT,
            font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"),
            height=34,
        )
        self.filter.pack(side="left")
        ghost_button(self.filter_bar, "Regras", lambda: self.main_window.navigate("rules"), width=100, height=34).pack(side="right")

        self.quick_filters = ctk.CTkFrame(self.scroll, fg_color="transparent")
        self.quick_filters.pack(fill="x", pady=(0, 12))
        self.date_menu = self._option_menu(
            self.quick_filters,
            self.date_filter_var,
            ["Qualquer data", "Recentes", "Antigas", "Sem data"],
        )
        self.date_menu.pack(side="left", padx=(0, 8))
        self.origin_menu = self._option_menu(
            self.quick_filters,
            self.origin_filter_var,
            ["Qualquer origem", "Drone", "Celular", "Camera", "Destino"],
        )
        self.origin_menu.pack(side="left", padx=(0, 8))
        self.quality_menu = self._option_menu(
            self.quick_filters,
            self.quality_filter_var,
            ["Qualquer qualidade", "Alta resolucao", "Baixa resolucao", "Sem EXIF", "Pesados"],
        )
        self.quality_menu.pack(side="left")

        body = ctk.CTkFrame(self.scroll, fg_color="transparent")
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=5)
        body.columnconfigure(1, weight=2)

        self.gallery_panel = ctk.CTkFrame(body, fg_color=SURFACE, corner_radius=8, border_width=1, border_color=BORDER)
        self.gallery_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        gal_head = ctk.CTkFrame(self.gallery_panel, fg_color="transparent")
        gal_head.pack(fill="x", padx=16, pady=(14, 8))
        ctk.CTkLabel(gal_head, text="Galeria", font=(FONT_FAMILY, FONT_SIZE_HEADER, "bold"), text_color=TEXT).pack(side="left")
        self.gallery_status = ctk.CTkLabel(gal_head, text="", font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_MUTED)
        self.gallery_status.pack(side="right")
        self.gallery_body = ctk.CTkFrame(self.gallery_panel, fg_color="transparent")
        self.gallery_body.pack(fill="x", padx=12, pady=(0, 12))

        self.insights_panel = ctk.CTkFrame(body, fg_color=SURFACE, corner_radius=8, border_width=1, border_color=BORDER)
        self.insights_panel.grid(row=0, column=1, sticky="nsew")
        ctk.CTkLabel(
            self.insights_panel,
            text="Insights",
            font=(FONT_FAMILY, FONT_SIZE_HEADER, "bold"),
            text_color=TEXT,
        ).pack(anchor="w", padx=16, pady=(14, 6))
        self.insights_body = ctk.CTkFrame(self.insights_panel, fg_color="transparent")
        self.insights_body.pack(fill="x", padx=12, pady=(0, 12))

        self.refresh()

    def _metric(self, col: int, title: str, value: str, subtitle: str):
        tile = ctk.CTkFrame(self.metrics, fg_color=SURFACE_ALT, corner_radius=8)
        tile.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 5, 0 if col == 3 else 5))
        ctk.CTkLabel(tile, text=title, font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_MUTED).pack(anchor="w", padx=12, pady=(10, 1))
        label = ctk.CTkLabel(tile, text=value, font=(FONT_FAMILY, 20, "bold"), text_color=TEXT)
        label.pack(anchor="w", padx=12)
        ctk.CTkLabel(tile, text=subtitle, font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_SUBTLE).pack(anchor="w", padx=12, pady=(0, 10))
        return label

    def _option_menu(self, parent, variable, values):
        return ctk.CTkOptionMenu(
            parent,
            values=values,
            variable=variable,
            command=lambda _value: self._load_gallery_async(force=True),
            fg_color=SURFACE,
            button_color=SURFACE_ALT,
            button_hover_color=ACCENT,
            dropdown_fg_color=SURFACE,
            dropdown_hover_color=SURFACE_ALT,
            text_color=TEXT,
            font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"),
            width=170,
            height=34,
        )

    def refresh(self):
        self._load_gallery_async()

    def _index_sources(self):
        if self._indexing:
            return
        sources = self._inventory_sources(include_destination=True)
        if not sources:
            self.hero_status.configure(text="Adicione fontes ou um destino antes de indexar o inventario.")
            return
        self._indexing = True
        self.hero_status.configure(text="Indexando metadados em modo somente leitura...")

        def worker():
            total_seen = 0
            try:
                from core.inventory import scan_inventory_source

                for source in sources:
                    root = Path(source.get("path", ""))
                    if not root.exists():
                        continue

                    def callback(_path, seen):
                        if seen % 50 == 0:
                            self.parent.after(
                                0,
                                lambda n=seen, label=root.name: self.hero_status.configure(
                                    text=f"Indexando {label}: {format_count(n)} arquivos lidos..."
                                ),
                            )
                        if seen <= 500 and seen % 5 == 0:
                            try:
                                from core.thumbnail_cache import ensure_thumbnail

                                ensure_thumbnail(_path)
                            except Exception:
                                pass

                    result = scan_inventory_source(
                        root,
                        label=source.get("label") or root.name,
                        source_type=source.get("type", "local"),
                        role=source.get("role", "origin"),
                        callback=callback,
                    )
                    total_seen += result.files_seen
                self.parent.after(0, lambda: self._index_done(total_seen, None))
            except Exception as exc:
                self.parent.after(0, lambda: self._index_done(total_seen, exc))

        threading.Thread(target=worker, daemon=True).start()

    def _index_done(self, total_seen: int, error):
        self._indexing = False
        if error:
            self.hero_status.configure(text=f"Falha ao indexar inventario: {error}")
            return
        self.hero_status.configure(text=f"Inventario atualizado com {format_count(total_seen)} arquivos lidos.")
        self._load_gallery_async(force=True)

    def _load_gallery_async(self, force: bool = False):
        if self._loading_gallery and not force:
            return
        self._loading_gallery = True
        self._gallery_gen += 1
        gen = self._gallery_gen
        self.gallery_status.configure(text="carregando...")
        self.hero_status.configure(text="Montando galeria e insights locais...")

        def worker():
            items = self._collect_items(GALLERY_LIMIT)
            duplicate_paths = self._duplicate_paths()
            summary = summarize_gallery(items, duplicate_paths)
            self.parent.after(0, lambda: self._render(items, summary, gen))

        threading.Thread(target=worker, daemon=True).start()

    def _collect_items(self, limit: int) -> list[GalleryItem]:
        sources = self._inventory_sources(include_destination=True)
        items: list[GalleryItem] = []
        try:
            from core.database import query_gallery_records

            records = query_gallery_records(self._db_filters(), limit=limit, offset=0)
            for record in records:
                item = item_from_record(record, sources)
                if item and self._belongs_to_current_sources(item.path, sources):
                    items.append(item)
            if items:
                return self._rank_items(items)
        except Exception:
            pass

        try:
            from core.scanner import scan_directory

            for source in sources:
                if source.get("type") == "cloud":
                    continue
                root = Path(source.get("path", ""))
                if not root.exists():
                    continue
                for path in scan_directory(root):
                    item = item_from_path(path, sources)
                    if item:
                        items.append(item)
                    if len(items) >= limit:
                        return self._rank_items(items)
        except Exception:
            pass
        return self._rank_items(items)

    def _db_filters(self) -> dict:
        filters = {}
        selected = self.filter_var.get()
        if selected == "Fotos":
            filters["media_type"] = "photo"
        elif selected == "Videos":
            filters["media_type"] = "video"
        elif selected == "Sem EXIF":
            filters["quality"] = "missing_exif"
        elif selected == "Pesados":
            filters["quality"] = "large"
        elif selected == "Problemas":
            filters["quality"] = "needs_review"

        date_selected = self.date_filter_var.get()
        if date_selected == "Recentes":
            filters["date_group"] = "recent"
        elif date_selected == "Antigas":
            filters["date_group"] = "older"
        elif date_selected == "Sem data":
            filters["date_group"] = "no_date"
        elif date_selected.isdigit():
            filters["date_group"] = date_selected

        origin_selected = self.origin_filter_var.get()
        if origin_selected == "Drone":
            filters["device_type"] = "drone"
        elif origin_selected == "Celular":
            filters["device_type"] = "phone"
        elif origin_selected == "Camera":
            filters["device_type"] = "camera"
        elif origin_selected == "Destino":
            filters["source_role"] = "destination"

        quality_selected = self.quality_filter_var.get()
        if quality_selected == "Alta resolucao":
            filters["quality"] = "high_resolution"
        elif quality_selected == "Baixa resolucao":
            filters["quality"] = "low_resolution"
        elif quality_selected == "Sem EXIF":
            filters["quality"] = "missing_exif"
        elif quality_selected == "Pesados":
            filters["quality"] = "large"
        return filters

    def _rank_items(self, items: list[GalleryItem]) -> list[GalleryItem]:
        duplicate_paths = self._duplicate_paths()

        def key(item: GalleryItem):
            duplicate_boost = 0 if str(item.path) in duplicate_paths else 1
            issue_boost = 0 if any(flag in item.flags for flag in ("Sem EXIF", "Baixa resolucao", "Muito pesado", "Sem data")) else 1
            date_key = item.date_taken.timestamp() if item.date_taken else 0
            return (duplicate_boost, issue_boost, -item.size, -date_key)

        return sorted(items, key=key)

    def _belongs_to_current_sources(self, path: Path, sources: list[dict]) -> bool:
        if not sources:
            return True
        p = str(path).lower()
        for source in sources:
            if source.get("type") == "cloud":
                continue
            root = str(source.get("path", "")).lower()
            if root and p.startswith(root):
                return True
        return False

    def _inventory_sources(self, include_destination: bool = False) -> list[dict]:
        sources = []
        seen = set()
        for source in self.app.app_state.get("sources", []):
            enriched = dict(source)
            enriched.setdefault("role", "origin")
            enriched.setdefault("label", Path(str(enriched.get("path", ""))).name or str(enriched.get("path", "")))
            root = Path(str(enriched.get("path", "")))
            key = self._source_key(root)
            seen.add(key)
            sources.append(enriched)
        try:
            from core.database import get_all_sources

            for source in get_all_sources():
                root = Path(source.get("root_path", ""))
                key = self._source_key(root)
                if key in seen:
                    continue
                seen.add(key)
                sources.append({
                    "path": root,
                    "label": source.get("label") or root.name or str(root),
                    "type": source.get("type") or "local",
                    "role": source.get("role") or "origin",
                })
        except Exception:
            pass
        if include_destination:
            destination = self.app.app_state.get("destination")
            if destination:
                dest_path = Path(destination)
                key = self._source_key(dest_path)
                if dest_path.exists():
                    if key not in seen:
                        sources.append({
                            "path": dest_path,
                            "label": "Biblioteca organizada",
                            "type": "destination",
                            "role": "destination",
                        })
        return sources

    def _source_key(self, path: Path) -> str:
        try:
            return str(path.resolve()).lower() if path.exists() else str(path).lower()
        except Exception:
            return str(path).lower()

    def _duplicate_paths(self) -> set[str]:
        dup = self.app.app_state.get("dup_result")
        paths: set[str] = set()
        if not dup:
            return paths
        for group in list(dup.exact.values()) + list(dup.visual.values()):
            for path in group:
                paths.add(str(path))
        return paths

    def _render(self, items: list[GalleryItem], summary: dict, gen: int):
        if gen != self._gallery_gen:
            return
        self._loading_gallery = False
        self._items = items
        self._summary = summary
        self._render_metrics()
        self._render_actions()
        self._render_insights()
        self._refresh_filter_options()
        self._render_gallery()

    def _render_metrics(self):
        total_size = sum(item.size for item in self._items)
        devices = {item.device_name for item in self._items if item.device_name}
        alerts = sum(1 for item in self._items if any(flag in item.flags for flag in ("Sem EXIF", "Baixa resolucao", "Muito pesado", "Sem data")))
        self.total_files_lbl.configure(text=format_count(len(self._items)))
        self.total_size_lbl.configure(text=format_size(total_size))
        self.device_count_lbl.configure(text=format_count(len(devices)))
        self.issue_count_lbl.configure(text=format_count(alerts))
        if self._items:
            self.hero_status.configure(
                text=f"Amostra inteligente com {format_count(len(self._items))} itens. Use filtros para priorizar limpeza e organizacao."
            )
        else:
            self.hero_status.configure(text="Sem dados visuais ainda. Adicione fontes ou rode a indexacao do inventario.")

    def _render_actions(self):
        self._clear(self.actions_body)
        for title, text in self._summary.get("actions", [])[:4]:
            self._insight_row(self.actions_body, title, text, accent=True)

    def _render_insights(self):
        self._clear(self.insights_body)
        if not self._items:
            empty_state(self.insights_body, "Indexe fontes para gerar insights.")
            return
        self._small_stat("Fotos", format_count(self._summary.get("photos", 0)), "imagens detectadas")
        self._small_stat("Videos", format_count(self._summary.get("videos", 0)), "arquivos de video")
        self._small_stat("Sem EXIF", format_count(self._summary.get("missing_exif", 0)), "precisam de data/origem")
        self._rank_list("Aparelhos", self._summary.get("devices", {}), 6)
        self._rank_list("Qualidade", self._summary.get("quality", {}), 6)
        self._rank_list("Meses", self._summary.get("date_groups", {}), 6)
        self._rank_list("Anos", self._summary.get("years", {}), 6)
        self._rank_list("Fontes", self._summary.get("sources", {}), 5)

    def _render_gallery(self):
        self._clear(self.gallery_body)
        items = self._filtered_items()
        self.gallery_status.configure(text=f"{format_count(len(items))} exibidos")
        if not items:
            empty_state(self.gallery_body, "Nenhum item neste filtro.")
            return
        grid = ctk.CTkFrame(self.gallery_body, fg_color="transparent")
        grid.pack(fill="x")
        for col in range(GRID_COLUMNS):
            grid.columnconfigure(col, weight=1, uniform="gallery")
        duplicate_paths = self._duplicate_paths()
        for idx, item in enumerate(items[:GALLERY_LIMIT]):
            self._gallery_card(grid, item, idx, str(item.path) in duplicate_paths)

    def _filtered_items(self) -> list[GalleryItem]:
        selected = self.filter_var.get()
        duplicate_paths = self._duplicate_paths()
        if selected == "Fotos":
            return [item for item in self._items if item.media_type == "photo"]
        if selected == "Videos":
            return [item for item in self._items if item.media_type == "video"]
        if selected == "Sem EXIF":
            return [item for item in self._items if not item.has_exif]
        if selected == "Pesados":
            return [item for item in self._items if item.size >= 50 * 1024 * 1024]
        if selected == "Problemas":
            return [item for item in self._items if any(flag in item.flags for flag in ("Sem EXIF", "Baixa resolucao", "Muito pesado", "Sem data", "Sem dimensoes"))]
        if selected == "Duplicados":
            return [item for item in self._items if str(item.path) in duplicate_paths]
        return self._items

    def _refresh_filter_options(self):
        years = [
            str(year) for year in sorted(self._summary.get("years", {}).keys(), reverse=True)
            if str(year).isdigit()
        ][:8]
        date_values = ["Qualquer data", "Recentes", "Antigas", "Sem data"] + years
        current = self.date_filter_var.get()
        self.date_menu.configure(values=date_values)
        if current not in date_values:
            self.date_filter_var.set("Qualquer data")

    def _gallery_card(self, parent, item: GalleryItem, idx: int, is_duplicate: bool):
        card = ctk.CTkFrame(parent, fg_color=SURFACE_ALT, corner_radius=8, border_width=1, border_color=ACCENT if is_duplicate else BORDER)
        card.grid(row=idx // GRID_COLUMNS, column=idx % GRID_COLUMNS, sticky="nsew", padx=6, pady=6)
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=8, pady=(8, 5))
        ctk.CTkLabel(top, text=item.media_type.upper(), font=(FONT_FAMILY, 10, "bold"), text_color=ACCENT if item.media_type == "video" else TEXT_MUTED).pack(side="left")
        ctk.CTkLabel(top, text=str(item.score), font=(FONT_FAMILY, 10, "bold"), text_color=TEXT).pack(side="right")

        thumb = ThumbnailViewer(card, item.path, size=(190, 126))
        thumb.pack(fill="x", padx=8)

        ctk.CTkLabel(
            card,
            text=item.name,
            font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"),
            text_color=TEXT,
            anchor="w",
            wraplength=185,
        ).pack(anchor="w", padx=9, pady=(7, 1))
        meta = f"{item.year} | {item.resolution_label} | {format_size(item.size)}"
        ctk.CTkLabel(card, text=meta, font=(FONT_FAMILY, 10), text_color=TEXT_MUTED, anchor="w", wraplength=185).pack(anchor="w", padx=9)
        ctk.CTkLabel(card, text=item.device_name, font=(FONT_FAMILY, 10), text_color=TEXT_SUBTLE, anchor="w", wraplength=185).pack(anchor="w", padx=9, pady=(1, 5))

        chips = ctk.CTkFrame(card, fg_color="transparent")
        chips.pack(fill="x", padx=8, pady=(0, 8))
        flags = list(item.chips or item.flags)
        if is_duplicate:
            flags.insert(0, "Duplicado")
        for flag in flags[:4]:
            self._chip(chips, flag)

    def _chip(self, parent, text: str):
        color = ACCENT_SOFT if text in {"Duplicado", "Sem EXIF", "Baixa res", "Baixa resolucao", "Muito pesado", "Sem data", "Pesado"} else SURFACE_MUTED
        label = ctk.CTkLabel(
            parent,
            text=text,
            font=(FONT_FAMILY, 9, "bold"),
            text_color=ACCENT if color == ACCENT_SOFT else TEXT_MUTED,
            fg_color=color,
            corner_radius=6,
            width=max(54, len(text) * 7),
            height=20,
        )
        label.pack(side="left", padx=(0, 4), pady=2)

    def _small_stat(self, title: str, value: str, subtitle: str):
        box = ctk.CTkFrame(self.insights_body, fg_color=SURFACE_ALT, corner_radius=8)
        box.pack(fill="x", pady=4)
        ctk.CTkLabel(box, text=title, font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=TEXT_MUTED).pack(anchor="w", padx=12, pady=(9, 0))
        ctk.CTkLabel(box, text=value, font=(FONT_FAMILY, 20, "bold"), text_color=TEXT).pack(anchor="w", padx=12)
        ctk.CTkLabel(box, text=subtitle, font=(FONT_FAMILY, 10), text_color=TEXT_SUBTLE).pack(anchor="w", padx=12, pady=(0, 9))

    def _rank_list(self, title: str, data: dict, limit: int):
        if not data:
            return
        ctk.CTkLabel(
            self.insights_body,
            text=title,
            font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"),
            text_color=TEXT,
        ).pack(anchor="w", padx=4, pady=(12, 4))
        max_count = max(data.values()) or 1
        for name, count in sorted(data.items(), key=lambda kv: kv[1], reverse=True)[:limit]:
            row = ctk.CTkFrame(self.insights_body, fg_color="transparent")
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=str(name), font=(FONT_FAMILY, 10), text_color=TEXT_MUTED, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=format_count(count), font=(FONT_FAMILY, 10, "bold"), text_color=TEXT).pack(side="right")
            bar = ctk.CTkFrame(self.insights_body, fg_color=SURFACE_MUTED, corner_radius=4, height=5)
            bar.pack(fill="x", pady=(0, 3))
            ctk.CTkFrame(bar, fg_color=ACCENT, corner_radius=4).place(relx=0, rely=0, relwidth=min(count / max_count, 1), relheight=1)

    def _insight_row(self, parent, title: str, text: str, accent: bool = False):
        row = ctk.CTkFrame(parent, fg_color=ACCENT_SOFT if accent else SURFACE_MUTED, corner_radius=8)
        row.pack(fill="x", pady=4)
        ctk.CTkLabel(row, text=title, font=(FONT_FAMILY, FONT_SIZE_SMALL, "bold"), text_color=ACCENT if accent else TEXT).pack(anchor="w", padx=10, pady=(8, 1))
        ctk.CTkLabel(row, text=text, font=(FONT_FAMILY, 10), text_color=TEXT_MUTED, wraplength=360, justify="left").pack(anchor="w", padx=10, pady=(0, 8))

    def _clear(self, frame):
        for child in frame.winfo_children():
            child.destroy()
