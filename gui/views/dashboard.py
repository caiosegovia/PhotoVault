import hashlib
import json
import threading
from datetime import datetime
import customtkinter as ctk
from gui.app import (COLOR_CARD, COLOR_TEXT, COLOR_TEXT_DIM, COLOR_ACCENT2,
                     COLOR_ACCENT, COLOR_BG, COLOR_SUCCESS, COLOR_WARNING,
                     COLOR_ERROR, COLOR_SIDEBAR, FONT_FAMILY, FONT_SIZE_TITLE,
                     FONT_SIZE_HEADER, FONT_SIZE_BODY, FONT_SIZE_SMALL)
from utils.formatting import format_size, format_count


# ── Big Number Card ────────────────────────────────────────────────────────────

class BigNumberCard(ctk.CTkFrame):
    def __init__(self, parent, title: str, value: str, subtitle: str,
                 icon: str, accent: str, **kw):
        super().__init__(parent, fg_color=COLOR_CARD, corner_radius=14, **kw)

        top = ctk.CTkFrame(self, fg_color='transparent')
        top.pack(fill='x', padx=18, pady=(18, 4))

        ctk.CTkLabel(top, text=icon, font=(FONT_FAMILY, 22)).pack(side='left')
        ctk.CTkLabel(
            top, text=title,
            font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=COLOR_TEXT_DIM
        ).pack(side='left', padx=8)

        self._value_lbl = ctk.CTkLabel(
            self, text=value,
            font=(FONT_FAMILY, 28, 'bold'), text_color=accent
        )
        self._value_lbl.pack(anchor='w', padx=18)

        self._sub_lbl = ctk.CTkLabel(
            self, text=subtitle,
            font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=COLOR_TEXT_DIM
        )
        self._sub_lbl.pack(anchor='w', padx=18, pady=(0, 18))

    def update(self, value: str, subtitle: str = None):
        self._value_lbl.configure(text=value)
        if subtitle is not None:
            self._sub_lbl.configure(text=subtitle)


# ── Source Card ───────────────────────────────────────────────────────────────

class SourceCard(ctk.CTkFrame):
    TYPE_META = {
        'local': ('📁', COLOR_ACCENT2,  'Pasta local'),
        'drive': ('💾', COLOR_ACCENT,   'Drive externo'),
        'cloud': ('☁',  COLOR_WARNING,  'Google Photos'),
    }

    def __init__(self, parent, src: dict, **kw):
        super().__init__(parent, fg_color='#0a2a50', corner_radius=10, **kw)

        src_type = src.get('type', 'local')
        icon, color, type_label = self.TYPE_META.get(src_type, ('📁', COLOR_ACCENT2, 'Fonte'))

        row = ctk.CTkFrame(self, fg_color='transparent')
        row.pack(fill='x', padx=14, pady=12)

        # Icon
        ctk.CTkLabel(row, text=icon, font=(FONT_FAMILY, 24)).pack(side='left', padx=(0, 12))

        # Info column
        info = ctk.CTkFrame(row, fg_color='transparent')
        info.pack(side='left', fill='x', expand=True)

        path_txt = src.get('path', '')
        ctk.CTkLabel(
            info, text=path_txt,
            font=(FONT_FAMILY, FONT_SIZE_BODY, 'bold'), text_color=COLOR_TEXT,
            anchor='w', wraplength=320
        ).pack(anchor='w')
        ctk.CTkLabel(
            info, text=type_label,
            font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=color, anchor='w'
        ).pack(anchor='w')

        # Stats column
        stats = ctk.CTkFrame(row, fg_color='transparent')
        stats.pack(side='right', padx=(12, 0))

        total = src.get('total', 0)
        photos = src.get('photos', 0)
        videos = src.get('videos', 0)
        size = src.get('size_bytes', 0)

        ctk.CTkLabel(
            stats, text=format_count(total),
            font=(FONT_FAMILY, 18, 'bold'), text_color=COLOR_TEXT
        ).pack(anchor='e')
        ctk.CTkLabel(
            stats, text='arquivos',
            font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=COLOR_TEXT_DIM
        ).pack(anchor='e')

        if total > 0:
            detail = f'📷 {format_count(photos)}  •  🎬 {format_count(videos)}'
            if size:
                detail += f'  •  {format_size(size)}'
            ctk.CTkLabel(
                info, text=detail,
                font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=COLOR_TEXT_DIM,
                anchor='w'
            ).pack(anchor='w', pady=(2, 0))


# ── Destination Analysis Card ─────────────────────────────────────────────────

class DestinationCard(ctk.CTkFrame):
    def __init__(self, parent, destination, **kw):
        super().__init__(parent, fg_color=COLOR_CARD, corner_radius=14, **kw)
        self._destination = destination
        self._build()
        self._scan()

    def _build(self):
        header = ctk.CTkFrame(self, fg_color='transparent')
        header.pack(fill='x', padx=18, pady=(14, 6))
        ctk.CTkLabel(header, text='🎯', font=(FONT_FAMILY, 18)).pack(side='left')
        ctk.CTkLabel(
            header, text='Destino',
            font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=COLOR_TEXT_DIM
        ).pack(side='left', padx=8)

        ctk.CTkLabel(
            self, text=str(self._destination),
            font=(FONT_FAMILY, FONT_SIZE_BODY, 'bold'), text_color=COLOR_TEXT,
            anchor='w', wraplength=500
        ).pack(anchor='w', padx=18)

        self._status_lbl = ctk.CTkLabel(
            self, text='Analisando destino...',
            font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=COLOR_TEXT_DIM,
            anchor='w'
        )
        self._status_lbl.pack(anchor='w', padx=18, pady=(4, 14))

        self._bar = ctk.CTkProgressBar(
            self, mode='indeterminate', height=4,
            fg_color='#2a2a4a', progress_color=COLOR_ACCENT
        )
        self._bar.pack(fill='x', padx=18, pady=(0, 4))
        self._bar.start()

    def _scan(self):
        def worker():
            from core.scanner import count_files
            try:
                counts = count_files(self._destination)
                self.after(0, lambda: self._show_result(counts))
            except Exception:
                self.after(0, lambda: self._status_lbl.configure(text='Erro ao analisar destino.'))

        threading.Thread(target=worker, daemon=True).start()

    def _show_result(self, counts: dict):
        self._bar.stop()
        self._bar.pack_forget()
        total = counts.get('total', 0)
        size = counts.get('size_bytes', 0)
        photos = counts.get('photos', 0)
        videos = counts.get('videos', 0)
        if total == 0:
            self._status_lbl.configure(
                text='Destino vazio — sem conflitos esperados.',
                text_color=COLOR_SUCCESS
            )
        else:
            txt = (f'{format_count(total)} arquivos já organizados  •  {format_size(size)}  •  '
                   f'📷 {format_count(photos)} fotos  •  🎬 {format_count(videos)} vídeos')
            self._status_lbl.configure(text=txt, text_color=COLOR_WARNING)


# ── Job History Card ──────────────────────────────────────────────────────────

class JobHistoryCard(ctk.CTkFrame):
    STATUS_META = {
        'completed': ('✓', COLOR_SUCCESS, 'Concluído'),
        'cancelled': ('✕', COLOR_WARNING, 'Cancelado'),
        'error':     ('✕', COLOR_ERROR,   'Erro'),
    }

    def __init__(self, parent, session, **kw):
        super().__init__(parent, fg_color='#0a1a30', corner_radius=10, **kw)
        self._build(dict(session))

    def _build(self, s: dict):
        status = s.get('status') or 'completed'
        icon, color, status_lbl = self.STATUS_META.get(status, ('✓', COLOR_SUCCESS, 'Concluído'))

        # Short hash ID derived from session id
        hash_id = hashlib.md5(str(s.get('id', 0)).encode()).hexdigest()[:8]

        # ── Header row ──────────────────────────────────────────────────────
        header = ctk.CTkFrame(self, fg_color='transparent')
        header.pack(fill='x', padx=14, pady=(12, 4))

        ctk.CTkLabel(
            header, text=icon,
            font=(FONT_FAMILY, 15, 'bold'), text_color=color, width=18
        ).pack(side='left')

        ctk.CTkLabel(
            header, text=f'Job #{hash_id}',
            font=(FONT_FAMILY, FONT_SIZE_BODY, 'bold'), text_color=COLOR_TEXT
        ).pack(side='left', padx=(6, 0))

        try:
            date_txt = (datetime.fromisoformat(s['started_at']).strftime('%d/%m/%Y %H:%M')
                        if s.get('started_at') else '—')
        except (ValueError, TypeError):
            date_txt = s.get('started_at') or '—'

        ctk.CTkLabel(
            header, text=date_txt,
            font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=COLOR_TEXT_DIM
        ).pack(side='left', padx=16)

        ctk.CTkLabel(
            header, text=status_lbl,
            font=(FONT_FAMILY, FONT_SIZE_SMALL, 'bold'), text_color=color
        ).pack(side='right')

        # ── Destination ─────────────────────────────────────────────────────
        dest = s.get('destination') or '—'
        ctk.CTkLabel(
            self, text=f'🎯 {dest}',
            font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=COLOR_TEXT_DIM,
            anchor='w', wraplength=650
        ).pack(anchor='w', padx=14, pady=(0, 6))

        # ── Progress bar ────────────────────────────────────────────────────
        processed = s.get('files_processed') or 0
        total = s.get('total_files') or 0
        if total == 0:
            total = processed or 1
        prog = min(processed / total, 1.0)

        bar_color = {
            'completed': COLOR_SUCCESS,
            'cancelled': COLOR_WARNING,
            'error': COLOR_ERROR,
        }.get(status, COLOR_SUCCESS)

        bar_row = ctk.CTkFrame(self, fg_color='transparent')
        bar_row.pack(fill='x', padx=14, pady=(0, 4))

        bar = ctk.CTkProgressBar(
            bar_row, height=8, corner_radius=4,
            fg_color='#2a2a4a', progress_color=bar_color
        )
        bar.set(prog)
        bar.pack(side='left', fill='x', expand=True, padx=(0, 10))

        ctk.CTkLabel(
            bar_row,
            text=f'{format_count(processed)} / {format_count(total)}',
            font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=COLOR_TEXT_DIM
        ).pack(side='right')

        # ── Summary stats row ───────────────────────────────────────────────
        try:
            sources_list = json.loads(s['sources']) if s.get('sources') else []
            n_sources = len(sources_list)
        except Exception:
            n_sources = 0

        errors = s.get('errors') or 0
        dups = s.get('duplicates_found') or 0
        freed = s.get('space_freed') or 0

        parts = [f'📁 {n_sources} fonte{"s" if n_sources != 1 else ""}']
        if processed:
            parts.append(f'✓ {format_count(processed)} processados')
        if errors:
            parts.append(f'✕ {errors} erros')
        if dups:
            parts.append(f'⧉ {format_count(dups)} dups')
        if freed:
            parts.append(f'♻ {format_size(freed)}')

        ctk.CTkLabel(
            self, text='  •  '.join(parts),
            font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=COLOR_TEXT_DIM,
            anchor='w'
        ).pack(anchor='w', padx=14, pady=(0, 12))


# ── Dashboard View ────────────────────────────────────────────────────────────

class DashboardView:
    def __init__(self, parent, app, main_window):
        self.parent = parent
        self.app = app
        self.main_window = main_window
        self._chart_sig = None   # track last chart data to avoid needless rebuilds
        self._dest_sig = None    # track last destination
        self._build()

    def _build(self):
        self.scroll = ctk.CTkScrollableFrame(self.parent, fg_color='transparent')
        self.scroll.pack(fill='both', expand=True, padx=20, pady=20)

        # Header
        header = ctk.CTkFrame(self.scroll, fg_color='transparent')
        header.pack(fill='x', pady=(0, 20))

        ctk.CTkLabel(
            header, text='Dashboard',
            font=(FONT_FAMILY, FONT_SIZE_TITLE, 'bold'), text_color=COLOR_TEXT
        ).pack(side='left')

        ctk.CTkButton(
            header, text='+ Nova Sessão',
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT2,
            corner_radius=8, width=140,
            command=self._new_session
        ).pack(side='right')

        # Big number cards (4 across)
        self._cards_frame = ctk.CTkFrame(self.scroll, fg_color='transparent')
        self._cards_frame.pack(fill='x', pady=(0, 20))
        for i in range(4):
            self._cards_frame.columnconfigure(i, weight=1, uniform='c')

        self.card_total = BigNumberCard(
            self._cards_frame, 'Arquivos', '—', 'total nas fontes', '🗂', COLOR_ACCENT2)
        self.card_total.grid(row=0, column=0, padx=(0, 8), sticky='ew')

        self.card_photos = BigNumberCard(
            self._cards_frame, 'Fotos', '—', '—', '📷', COLOR_ACCENT)
        self.card_photos.grid(row=0, column=1, padx=8, sticky='ew')

        self.card_videos = BigNumberCard(
            self._cards_frame, 'Vídeos', '—', '—', '🎬', COLOR_ACCENT2)
        self.card_videos.grid(row=0, column=2, padx=8, sticky='ew')

        self.card_size = BigNumberCard(
            self._cards_frame, 'Espaço', '—', 'total nas fontes', '💾', COLOR_SUCCESS)
        self.card_size.grid(row=0, column=3, padx=(8, 0), sticky='ew')

        # Second row: dups + freed
        self._cards2_frame = ctk.CTkFrame(self.scroll, fg_color='transparent')
        self._cards2_frame.pack(fill='x', pady=(0, 20))
        self._cards2_frame.columnconfigure(0, weight=1)
        self._cards2_frame.columnconfigure(1, weight=1)

        self.card_dups = BigNumberCard(
            self._cards2_frame, 'Grupos Duplicados', '—', 'exatos + visuais', '⧉', COLOR_WARNING)
        self.card_dups.grid(row=0, column=0, padx=(0, 8), sticky='ew')

        self.card_freed = BigNumberCard(
            self._cards2_frame, 'Espaço Liberável', '—', 'de duplicatas', '♻', COLOR_SUCCESS)
        self.card_freed.grid(row=0, column=1, padx=(8, 0), sticky='ew')

        # Charts row
        charts_row = ctk.CTkFrame(self.scroll, fg_color='transparent')
        charts_row.pack(fill='x', pady=(0, 20))
        charts_row.columnconfigure(0, weight=1)
        charts_row.columnconfigure(1, weight=2)

        donut_frame = ctk.CTkFrame(charts_row, fg_color=COLOR_CARD, corner_radius=12)
        donut_frame.grid(row=0, column=0, padx=(0, 10), sticky='nsew')
        ctk.CTkLabel(
            donut_frame, text='Distribuição por Tipo',
            font=(FONT_FAMILY, FONT_SIZE_HEADER, 'bold'), text_color=COLOR_TEXT
        ).pack(pady=(16, 4))
        self.donut_container = ctk.CTkFrame(donut_frame, fg_color='transparent', height=200)
        self.donut_container.pack(fill='x', padx=10, pady=(0, 16))

        bar_frame = ctk.CTkFrame(charts_row, fg_color=COLOR_CARD, corner_radius=12)
        bar_frame.grid(row=0, column=1, padx=(10, 0), sticky='nsew')
        ctk.CTkLabel(
            bar_frame, text='Fotos por Ano',
            font=(FONT_FAMILY, FONT_SIZE_HEADER, 'bold'), text_color=COLOR_TEXT
        ).pack(pady=(16, 4))
        self.bar_container = ctk.CTkFrame(bar_frame, fg_color='transparent', height=200)
        self.bar_container.pack(fill='x', padx=10, pady=(0, 16))

        # Sources section
        ctk.CTkLabel(
            self.scroll, text='Fontes Adicionadas',
            font=(FONT_FAMILY, FONT_SIZE_HEADER, 'bold'), text_color=COLOR_TEXT
        ).pack(anchor='w', pady=(0, 8))

        self.sources_container = ctk.CTkFrame(self.scroll, fg_color='transparent')
        self.sources_container.pack(fill='x', pady=(0, 20))

        # Destination section
        ctk.CTkLabel(
            self.scroll, text='Destino Configurado',
            font=(FONT_FAMILY, FONT_SIZE_HEADER, 'bold'), text_color=COLOR_TEXT
        ).pack(anchor='w', pady=(0, 8))

        self.dest_container = ctk.CTkFrame(self.scroll, fg_color='transparent')
        self.dest_container.pack(fill='x', pady=(0, 20))

        # Recent sessions
        ctk.CTkLabel(
            self.scroll, text='Sessões Recentes',
            font=(FONT_FAMILY, FONT_SIZE_HEADER, 'bold'), text_color=COLOR_TEXT
        ).pack(anchor='w', pady=(0, 8))

        self.sessions_frame = ctk.CTkFrame(self.scroll, fg_color=COLOR_CARD, corner_radius=12)
        self.sessions_frame.pack(fill='x')

    # ── refresh ────────────────────────────────────────────────────────────────

    def refresh(self):
        state = self.app.app_state
        results = state.get('scan_results') or {}
        dup = state.get('dup_result')

        total = results.get('total', 0)
        photos = results.get('photos', 0)
        videos = results.get('videos', 0)
        others = results.get('others', 0)
        size = results.get('size_bytes', 0)

        # Update big number cards
        sources = state.get('sources', [])
        n_sources = len(sources)
        src_txt = f'{n_sources} fonte{"s" if n_sources != 1 else ""} adicionada{"s" if n_sources != 1 else ""}'

        self.card_total.update(format_count(total) if total else '—', src_txt)
        self.card_photos.update(
            format_count(photos) if photos else '—',
            f'{int(photos / total * 100)}% do total' if total else '—'
        )
        self.card_videos.update(
            format_count(videos) if videos else '—',
            f'{int(videos / total * 100)}% do total' if total else '—'
        )
        self.card_size.update(
            format_size(size) if size else '—',
            f'{format_count(others)} outros' if others else 'nas fontes'
        )

        dup_count = 0
        space_wasted = 0
        if dup:
            dup_count = len(dup.exact) + len(dup.visual)
            space_wasted = dup.space_wasted
        self.card_dups.update(
            format_count(dup_count) if dup else '—',
            'exatos + visuais' if dup else 'execute a detecção'
        )
        self.card_freed.update(
            format_size(space_wasted) if dup else '—',
            'de duplicatas' if dup else 'execute a detecção'
        )

        self._refresh_sources(sources)
        self._refresh_destination(state.get('destination'))
        self._refresh_charts(results)
        self._load_sessions()

    def _refresh_sources(self, sources: list):
        for w in self.sources_container.winfo_children():
            w.destroy()
        if not sources:
            ctk.CTkLabel(
                self.sources_container,
                text='Nenhuma fonte adicionada. Vá em Fontes para adicionar.',
                font=(FONT_FAMILY, FONT_SIZE_BODY), text_color=COLOR_TEXT_DIM
            ).pack(anchor='w', pady=8)
            return
        for src in sources:
            SourceCard(self.sources_container, src).pack(fill='x', pady=4)

    def _refresh_destination(self, destination):
        dest_key = str(destination) if destination else None
        if dest_key == self._dest_sig:
            return  # same destination, no need to rescan
        self._dest_sig = dest_key
        for w in self.dest_container.winfo_children():
            w.destroy()
        if not destination:
            ctk.CTkLabel(
                self.dest_container,
                text='Nenhum destino configurado. Vá em Regras para definir.',
                font=(FONT_FAMILY, FONT_SIZE_BODY), text_color=COLOR_TEXT_DIM
            ).pack(anchor='w', pady=8)
            return
        DestinationCard(self.dest_container, destination).pack(fill='x')

    def _refresh_charts(self, results: dict):
        photos = results.get('photos', 0)
        videos = results.get('videos', 0)
        others = results.get('others', 0)

        # Skip expensive chart rebuild if data hasn't changed
        sig = (photos, videos, others)
        if sig == self._chart_sig:
            return
        self._chart_sig = sig

        for w in self.donut_container.winfo_children():
            w.destroy()
        for w in self.bar_container.winfo_children():
            w.destroy()

        try:
            from gui.widgets.storage_chart import StorageDonutChart, StorageBarChart
            if photos + videos + others > 0:
                StorageDonutChart(
                    self.donut_container,
                    data={'Fotos': photos, 'Vídeos': videos, 'Outros': others}
                ).pack(fill='both', expand=True)
            else:
                ctk.CTkLabel(
                    self.donut_container, text='Nenhum arquivo escaneado ainda.',
                    text_color=COLOR_TEXT_DIM, font=(FONT_FAMILY, FONT_SIZE_BODY)
                ).pack(expand=True, pady=40)

            try:
                from core.database import get_files_by_year
                year_data = get_files_by_year()
            except Exception:
                year_data = {}
            StorageBarChart(self.bar_container, data=year_data).pack(fill='both', expand=True)
        except Exception:
            ctk.CTkLabel(
                self.donut_container, text='Gráfico indisponível',
                text_color=COLOR_TEXT_DIM
            ).pack(expand=True, pady=40)

    def _load_sessions(self):
        for w in self.sessions_frame.winfo_children():
            w.destroy()
        try:
            from core.database import get_scan_history
            sessions = get_scan_history(8)
            if not sessions:
                ctk.CTkLabel(
                    self.sessions_frame, text='Nenhuma sessão registrada ainda.',
                    text_color=COLOR_TEXT_DIM, font=(FONT_FAMILY, FONT_SIZE_BODY)
                ).pack(pady=20)
                return
            for s in sessions:
                JobHistoryCard(self.sessions_frame, s).pack(
                    fill='x', padx=12, pady=6
                )
        except Exception:
            ctk.CTkLabel(
                self.sessions_frame, text='Banco de dados não inicializado.',
                text_color=COLOR_TEXT_DIM, font=(FONT_FAMILY, FONT_SIZE_BODY)
            ).pack(pady=20)

    def _new_session(self):
        self.app.app_state['sources'] = []
        self.app.app_state['scan_results'] = None
        self.app.app_state['plan'] = None
        self.app.app_state['dup_result'] = None
        self.main_window.navigate('sources')
