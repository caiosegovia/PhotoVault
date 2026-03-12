import hashlib
import json
import threading
import logging
from datetime import datetime
from pathlib import Path
import customtkinter as ctk
from gui.app import (COLOR_CARD, COLOR_TEXT, COLOR_TEXT_DIM, COLOR_ACCENT2,
                     COLOR_ACCENT, COLOR_BG, COLOR_SUCCESS, COLOR_WARNING,
                     COLOR_ERROR, COLOR_SIDEBAR, COLOR_BORDER, FONT_FAMILY, 
                     FONT_SIZE_TITLE, FONT_SIZE_HEADER, FONT_SIZE_BODY, FONT_SIZE_SMALL)
from utils.formatting import format_size, format_count

logger = logging.getLogger(__name__)

# ── Big Number Card ────────────────────────────────────────────────────────────

class BigNumberCard(ctk.CTkFrame):
    def __init__(self, parent, title: str, value: str, subtitle: str,
                 icon: str, accent: str, **kw):
        super().__init__(parent, fg_color=COLOR_CARD, corner_radius=16, 
                         border_color=COLOR_BORDER, border_width=1, **kw)

        self.grid_columnconfigure(0, weight=1)
        
        # Header
        header = ctk.CTkFrame(self, fg_color='transparent')
        header.pack(fill='x', padx=20, pady=(18, 2))

        ctk.CTkLabel(header, text=icon, font=(FONT_FAMILY, 22)).pack(side='left')
        ctk.CTkLabel(
            header, text=title,
            font=(FONT_FAMILY, FONT_SIZE_SMALL, 'bold'), text_color=COLOR_TEXT_DIM
        ).pack(side='left', padx=10)

        # Value
        self._value_lbl = ctk.CTkLabel(
            self, text=value,
            font=(FONT_FAMILY, 32, 'bold'), text_color=accent
        )
        self._value_lbl.pack(anchor='w', padx=20, pady=(4, 2))

        # Subtitle
        self._sub_lbl = ctk.CTkLabel(
            self, text=subtitle,
            font=(FONT_FAMILY, 11), text_color=COLOR_TEXT_DIM
        )
        self._sub_lbl.pack(anchor='w', padx=20, pady=(0, 18))

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
        super().__init__(parent, fg_color=COLOR_BG, corner_radius=12, 
                         border_color=COLOR_BORDER, border_width=1, **kw)

        src_type = src.get('type', 'local')
        icon, color, type_label = self.TYPE_META.get(src_type, ('📁', COLOR_ACCENT2, 'Fonte'))

        row = ctk.CTkFrame(self, fg_color='transparent')
        row.pack(fill='x', padx=16, pady=14)

        # Icon
        ctk.CTkLabel(row, text=icon, font=(FONT_FAMILY, 26)).pack(side='left', padx=(0, 14))

        # Info column
        info = ctk.CTkFrame(row, fg_color='transparent')
        info.pack(side='left', fill='x', expand=True)

        path_txt = src.get('path', '')
        ctk.CTkLabel(
            info, text=path_txt,
            font=(FONT_FAMILY, FONT_SIZE_BODY, 'bold'), text_color=COLOR_TEXT,
            anchor='w', wraplength=400
        ).pack(anchor='w')
        ctk.CTkLabel(
            info, text=type_label,
            font=(FONT_FAMILY, 11), text_color=color, anchor='w'
        ).pack(anchor='w')

        # Stats column
        stats = ctk.CTkFrame(row, fg_color='transparent')
        stats.pack(side='right', padx=(14, 0))

        total = src.get('total', 0)
        size = src.get('size_bytes', 0)

        ctk.CTkLabel(
            stats, text=format_count(total),
            font=(FONT_FAMILY, 20, 'bold'), text_color=COLOR_TEXT
        ).pack(anchor='e')
        ctk.CTkLabel(
            stats, text=format_size(size),
            font=(FONT_FAMILY, 11), text_color=COLOR_TEXT_DIM
        ).pack(anchor='e')


# ── Destination Analysis Card ─────────────────────────────────────────────────

class DestinationCard(ctk.CTkFrame):
    def __init__(self, parent, destination, app, **kw):
        super().__init__(parent, fg_color=COLOR_CARD, corner_radius=16, 
                         border_color=COLOR_BORDER, border_width=1, **kw)
        self._destination = destination
        self.app = app
        self._build()
        self._scan()

    def _build(self):
        header = ctk.CTkFrame(self, fg_color='transparent')
        header.pack(fill='x', padx=20, pady=(16, 4))
        ctk.CTkLabel(header, text='🎯', font=(FONT_FAMILY, 20)).pack(side='left')
        ctk.CTkLabel(
            header, text='Destino Principal',
            font=(FONT_FAMILY, FONT_SIZE_SMALL, 'bold'), text_color=COLOR_TEXT_DIM
        ).pack(side='left', padx=10)

        ctk.CTkLabel(
            self, text=str(self._destination),
            font=(FONT_FAMILY, FONT_SIZE_BODY, 'bold'), text_color=COLOR_TEXT,
            anchor='w', wraplength=500
        ).pack(anchor='w', padx=20, pady=(4, 2))

        self._status_lbl = ctk.CTkLabel(
            self, text='Analisando estrutura do destino...',
            font=(FONT_FAMILY, 11), text_color=COLOR_TEXT_DIM,
            anchor='w'
        )
        self._status_lbl.pack(anchor='w', padx=20, pady=(4, 16))

        self._bar = ctk.CTkProgressBar(
            self, mode='indeterminate', height=4, corner_radius=2,
            fg_color=COLOR_BG, progress_color=COLOR_ACCENT
        )
        self._bar.pack(fill='x', padx=20, pady=(0, 16))
        self._bar.start()

    def _scan(self):
        def worker():
            from core.scanner import count_files
            try:
                counts = count_files(self._destination)
                if self.winfo_exists():
                    self.after(0, lambda: self._show_result(counts))
            except Exception:
                if self.winfo_exists():
                    self.after(0, lambda: self._status_lbl.configure(text='Erro ao analisar destino.', text_color=COLOR_ERROR))

        if hasattr(self.app, 'executor'):
            self.app.executor.submit(worker)
        else:
            threading.Thread(target=worker, daemon=True).start()

    def _show_result(self, counts: dict):
        self._bar.stop()
        self._bar.pack_forget()
        total = counts.get('total', 0)
        size = counts.get('size_bytes', 0)
        if total == 0:
            self._status_lbl.configure(text='Vazio — Pronto para receber novos arquivos.', text_color=COLOR_SUCCESS)
        else:
            txt = f'{format_count(total)} arquivos encontrados  •  {format_size(size)} ocupados'
            self._status_lbl.configure(text=txt, text_color=COLOR_WARNING)


# ── Job History Card ──────────────────────────────────────────────────────────

class JobHistoryCard(ctk.CTkFrame):
    STATUS_META = {
        'completed': ('✓', COLOR_SUCCESS, 'Concluído'),
        'cancelled': ('✕', COLOR_WARNING, 'Cancelado'),
        'error':     ('✕', COLOR_ERROR,   'Erro'),
    }

    def __init__(self, parent, session, **kw):
        super().__init__(parent, fg_color=COLOR_BG, corner_radius=12, 
                         border_color=COLOR_BORDER, border_width=1, **kw)
        self._build(dict(session))

    def _build(self, s: dict):
        status = s.get('status') or 'completed'
        icon, color, status_lbl = self.STATUS_META.get(status, ('✓', COLOR_SUCCESS, 'Concluído'))
        hash_id = hashlib.md5(str(s.get('id', 0)).encode()).hexdigest()[:6].upper()

        header = ctk.CTkFrame(self, fg_color='transparent')
        header.pack(fill='x', padx=16, pady=(14, 4))

        ctk.CTkLabel(header, text=icon, font=(FONT_FAMILY, 14, 'bold'), text_color=color).pack(side='left')
        ctk.CTkLabel(header, text=f'JOB #{hash_id}', font=(FONT_FAMILY, 12, 'bold'), text_color=COLOR_TEXT).pack(side='left', padx=8)

        try:
            date_txt = datetime.fromisoformat(s['started_at']).strftime('%d/%m/%Y %H:%M') if s.get('started_at') else '—'
        except Exception: date_txt = '—'
        ctk.CTkLabel(header, text=date_txt, font=(FONT_FAMILY, 11), text_color=COLOR_TEXT_DIM).pack(side='left', padx=12)
        ctk.CTkLabel(header, text=status_lbl, font=(FONT_FAMILY, 11, 'bold'), text_color=color).pack(side='right')

        dest = s.get('destination') or '—'
        ctk.CTkLabel(self, text=f'🎯 {dest}', font=(FONT_FAMILY, 11), text_color=COLOR_TEXT_DIM, anchor='w', wraplength=600).pack(anchor='w', padx=16, pady=(0, 8))

        processed = s.get('files_processed') or 0
        total = s.get('total_files') or 1
        prog = min(processed / total, 1.0)
        
        bar = ctk.CTkProgressBar(self, height=6, corner_radius=3, fg_color=COLOR_SIDEBAR, progress_color=color)
        bar.set(prog)
        bar.pack(fill='x', padx=16, pady=(0, 14))


# ── Dashboard View ────────────────────────────────────────────────────────────

class DashboardView:
    def __init__(self, parent, app, main_window):
        self.parent = parent
        self.app = app
        self.main_window = main_window
        self._chart_sig = None
        self._dest_sig = None
        self._build()

    def _build(self):
        self.scroll = ctk.CTkScrollableFrame(self.parent, fg_color='transparent')
        self.scroll.pack(fill='both', expand=True, padx=30, pady=30)

        header = ctk.CTkFrame(self.scroll, fg_color='transparent')
        header.pack(fill='x', pady=(0, 30))

        welcome = ctk.CTkFrame(header, fg_color='transparent')
        welcome.pack(side='left')
        ctk.CTkLabel(welcome, text='Visão Geral', font=(FONT_FAMILY, FONT_SIZE_TITLE, 'bold'), text_color=COLOR_TEXT).pack(anchor='w')
        ctk.CTkLabel(welcome, text='Bem-vindo ao PhotoVault. Gerencie suas memórias com facilidade.', font=(FONT_FAMILY, FONT_SIZE_BODY), text_color=COLOR_TEXT_DIM).pack(anchor='w')

        ctk.CTkButton(header, text='🚀  Nova Organização', font=(FONT_FAMILY, FONT_SIZE_BODY, 'bold'), fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT2, corner_radius=10, width=220, height=44, command=self._new_session).pack(side='right')

        # Row 1
        r1 = ctk.CTkFrame(self.scroll, fg_color='transparent')
        r1.pack(fill='x', pady=(0, 12))
        for i in range(4): r1.columnconfigure(i, weight=1, uniform='r1')
        self.card_total = BigNumberCard(r1, 'ARQUIVOS', '—', 'total nas fontes', '🗂', COLOR_ACCENT2)
        self.card_total.grid(row=0, column=0, padx=(0, 6), sticky='ew')
        self.card_photos = BigNumberCard(r1, 'FOTOS', '—', '—', '📷', COLOR_ACCENT)
        self.card_photos.grid(row=0, column=1, padx=6, sticky='ew')
        self.card_videos = BigNumberCard(r1, 'VÍDEOS', '—', '—', '🎬', COLOR_ACCENT2)
        self.card_videos.grid(row=0, column=2, padx=6, sticky='ew')
        self.card_size = BigNumberCard(r1, 'ARMAZENAMENTO', '—', 'total detectado', '💾', COLOR_SUCCESS)
        self.card_size.grid(row=0, column=3, padx=(6, 0), sticky='ew')

        # Row 2
        r2 = ctk.CTkFrame(self.scroll, fg_color='transparent')
        r2.pack(fill='x', pady=(0, 24))
        for i in range(3): r2.columnconfigure(i, weight=1, uniform='r2')
        self.card_dups = BigNumberCard(r2, 'DUPLICATAS', '—', 'grupos detectados', '⧉', COLOR_WARNING)
        self.card_dups.grid(row=0, column=0, padx=(0, 6), sticky='ew')
        self.card_freed = BigNumberCard(r2, 'RECUPERÁVEL', '—', 'espaço em duplicatas', '♻', COLOR_SUCCESS)
        self.card_freed.grid(row=0, column=1, padx=6, sticky='ew')
        self.card_drive = BigNumberCard(r2, 'DISCO DESTINO', '—', 'espaço livre', '💽', COLOR_ACCENT2)
        self.card_drive.grid(row=0, column=2, padx=(6, 0), sticky='ew')

        # Charts & Dest
        mid = ctk.CTkFrame(self.scroll, fg_color='transparent')
        mid.pack(fill='x', pady=(0, 30))
        mid.columnconfigure(0, weight=2)
        mid.columnconfigure(1, weight=1)

        cframe = ctk.CTkFrame(mid, fg_color=COLOR_CARD, corner_radius=16, border_color=COLOR_BORDER, border_width=1)
        cframe.grid(row=0, column=0, padx=(0, 10), sticky='nsew')
        ctk.CTkLabel(cframe, text='Análise de Dados', font=(FONT_FAMILY, FONT_SIZE_HEADER, 'bold')).pack(anchor='w', padx=20, pady=18)
        inner = ctk.CTkFrame(cframe, fg_color='transparent')
        inner.pack(fill='both', expand=True, padx=10, pady=(0, 20))
        inner.columnconfigure(0, weight=1); inner.columnconfigure(1, weight=1)
        self.donut_container = ctk.CTkFrame(inner, fg_color='transparent', height=220); self.donut_container.grid(row=0, column=0, sticky='nsew')
        self.size_bar_container = ctk.CTkFrame(inner, fg_color='transparent', height=220); self.size_bar_container.grid(row=0, column=1, sticky='nsew')

        dest_side = ctk.CTkFrame(mid, fg_color='transparent')
        dest_side.grid(row=0, column=1, padx=(10, 0), sticky='nsew')
        ctk.CTkLabel(dest_side, text='Fontes & Destino', font=(FONT_FAMILY, FONT_SIZE_HEADER, 'bold')).pack(anchor='w', pady=(0, 12))
        self.dest_container = ctk.CTkFrame(dest_side, fg_color='transparent')
        self.dest_container.pack(fill='both', expand=True)

        ctk.CTkLabel(self.scroll, text='Histórico de Atividade', font=(FONT_FAMILY, FONT_SIZE_HEADER, 'bold')).pack(anchor='w', pady=(10, 12))
        self.sessions_frame = ctk.CTkFrame(self.scroll, fg_color=COLOR_CARD, corner_radius=16, border_color=COLOR_BORDER, border_width=1)
        self.sessions_frame.pack(fill='x')

    def refresh(self):
        state = self.app.app_state
        res = state.get('scan_results') or {}
        dup = state.get('dup_result')
        
        total = res.get('total', 0)
        self.card_total.update(format_count(total) if total else '—', f'{len(state.get("sources", []))} fontes')
        self.card_photos.update(format_count(res.get('photos', 0)) if total else '—', f'{int(res.get("photos", 0)/total*100) if total else 0}%')
        self.card_videos.update(format_count(res.get('videos', 0)) if total else '—', f'{int(res.get("videos", 0)/total*100) if total else 0}%')
        self.card_size.update(format_size(res.get('size_bytes', 0)) if total else '—', 'total detectado')

        dup_g = (len(dup.exact) + len(dup.visual)) if dup else 0
        self.card_dups.update(format_count(dup_g) if dup else '—', 'grupos detectados')
        self.card_freed.update(format_size(dup.space_wasted) if dup else '—', 'espaço recuperável')

        dest = state.get('destination')
        if dest:
            from core.scanner import get_drive_info
            dinfo = get_drive_info(Path(dest))
            self.card_drive.update(format_size(dinfo.get('free_space', 0)), 'espaço livre no destino')
        else: self.card_drive.update('—', 'destino não definido')

        self._refresh_destination(dest)
        self._refresh_charts(res)
        self._load_sessions()

    def _refresh_destination(self, destination):
        if str(destination) == self._dest_sig: return
        self._dest_sig = str(destination)
        for w in self.dest_container.winfo_children(): w.destroy()
        if not destination:
            ctk.CTkLabel(self.dest_container, text='Nenhum destino configurado.', font=(FONT_FAMILY, 13), text_color=COLOR_TEXT_DIM).pack(pady=10)
        else: DestinationCard(self.dest_container, destination, self.app).pack(fill='x')
        
        sources = self.app.app_state.get('sources', [])
        for src in sources[:2]: # Show only first 2 for dashboard brevity
            SourceCard(self.dest_container, src).pack(fill='x', pady=(8, 0))

    def _refresh_charts(self, results):
        sig = (results.get('photos', 0), results.get('photos_size', 0))
        if sig == self._chart_sig: return
        self._chart_sig = sig
        for w in self.donut_container.winfo_children(): w.destroy()
        for w in self.size_bar_container.winfo_children(): w.destroy()
        try:
            from gui.widgets.storage_chart import StorageDonutChart, StorageSizeBarChart
            if results.get('total', 0) > 0:
                StorageDonutChart(self.donut_container, data={'Fotos': results.get('photos', 0), 'Vídeos': results.get('videos', 0), 'Outros': results.get('others', 0)}).pack(fill='both', expand=True)
                StorageSizeBarChart(self.size_bar_container, data={'Fotos': results.get('photos_size', 0), 'Vídeos': results.get('videos_size', 0), 'Outros': results.get('others_size', 0)}).pack(fill='both', expand=True)
        except Exception: logger.exception("Dashboard chart error")

    def _load_sessions(self):
        for w in self.sessions_frame.winfo_children(): w.destroy()
        try:
            from core.database import get_scan_history
            sessions = get_scan_history(5)
            if not sessions: ctk.CTkLabel(self.sessions_frame, text='Sem histórico.', text_color=COLOR_TEXT_DIM).pack(pady=20)
            else:
                for s in sessions: JobHistoryCard(self.sessions_frame, s).pack(fill='x', padx=16, pady=8)
        except Exception: logger.exception("Dashboard history error")

    def _new_session(self):
        self.app.app_state.update({'sources': [], 'scan_results': None, 'plan': None, 'dup_result': None})
        self.main_window.navigate('sources')
