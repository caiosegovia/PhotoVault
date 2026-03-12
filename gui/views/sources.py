import threading
import logging
import customtkinter as ctk
from pathlib import Path
from tkinter import filedialog
from gui.app import (COLOR_CARD, COLOR_TEXT, COLOR_TEXT_DIM, COLOR_ACCENT,
                     COLOR_ACCENT2, COLOR_BG, COLOR_SUCCESS, COLOR_ERROR,
                     COLOR_BORDER, FONT_FAMILY, FONT_SIZE_TITLE, 
                     FONT_SIZE_HEADER, FONT_SIZE_BODY, FONT_SIZE_SMALL)
from utils.formatting import format_size, format_count

logger = logging.getLogger(__name__)

class SourcesView:
    def __init__(self, parent, app, main_window):
        self.parent = parent
        self.app = app
        self.main_window = main_window
        self._scanning = False
        self._build()

    def _build(self):
        self.container = ctk.CTkFrame(self.parent, fg_color='transparent')
        self.container.pack(fill='both', expand=True, padx=30, pady=30)

        # Header
        header = ctk.CTkFrame(self.container, fg_color='transparent')
        header.pack(fill='x', pady=(0, 24))

        title_frame = ctk.CTkFrame(header, fg_color='transparent')
        title_frame.pack(side='left')
        
        ctk.CTkLabel(
            title_frame, text='Fontes de Mídia',
            font=(FONT_FAMILY, FONT_SIZE_TITLE, 'bold'), text_color=COLOR_TEXT
        ).pack(anchor='w')
        
        ctk.CTkLabel(
            title_frame, text='Adicione as pastas onde suas fotos e vídeos estão armazenados.',
            font=(FONT_FAMILY, FONT_SIZE_BODY), text_color=COLOR_TEXT_DIM
        ).pack(anchor='w')

        # Add buttons
        btn_frame = ctk.CTkFrame(header, fg_color='transparent')
        btn_frame.pack(side='right')

        self.add_btn = ctk.CTkButton(
            btn_frame, text='📂  Adicionar Pasta',
            font=(FONT_FAMILY, FONT_SIZE_BODY, 'bold'),
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT2,
            corner_radius=10, width=180, height=44,
            command=self._add_folder
        )
        self.add_btn.pack(side='left', padx=10)

        # Main Content: Scrollable list of sources
        self.scroll = ctk.CTkScrollableFrame(
            self.container, fg_color=COLOR_CARD, corner_radius=16,
            border_color=COLOR_BORDER, border_width=1
        )
        self.scroll.pack(fill='both', expand=True, pady=(0, 24))

        # Bottom Bar
        footer = ctk.CTkFrame(self.container, fg_color='transparent')
        footer.pack(fill='x')

        self.status_lbl = ctk.CTkLabel(
            footer, text='Nenhuma fonte adicionada.',
            font=(FONT_FAMILY, FONT_SIZE_BODY), text_color=COLOR_TEXT_DIM
        )
        self.status_lbl.pack(side='left')

        self.next_btn = ctk.CTkButton(
            footer, text='Próximo: Regras  ▶',
            font=(FONT_FAMILY, FONT_SIZE_BODY, 'bold'),
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT2,
            corner_radius=10, width=200, height=44,
            command=self._continue
        )
        self.next_btn.pack(side='right')

    def _add_folder(self):
        folder = filedialog.askdirectory(title="Selecionar Pasta de Fotos/Vídeos")
        if not folder: return
        
        path = Path(folder)
        if any(s['path'] == str(path) for s in self.app.app_state['sources']):
            return # Already added

        logger.info(f"Adding source folder: {path}")
        source_item = {
            'path': str(path),
            'type': 'local',
            'total': 0, 'photos': 0, 'videos': 0, 'size_bytes': 0,
            'status': 'scanning'
        }
        self.app.app_state['sources'].append(source_item)
        self._refresh_list()
        self._scan_source(source_item)

    def _scan_source(self, source_item):
        def worker():
            from core.scanner import count_files
            try:
                results = count_files(Path(source_item['path']))
                source_item.update(results)
                source_item['status'] = 'ready'
                self.after(0, self._on_scan_done)
            except Exception:
                logger.exception(f"Failed to scan source: {source_item['path']}")
                source_item['status'] = 'error'
                self.after(0, self._refresh_list)

        if hasattr(self.app, 'executor'):
            self.app.executor.submit(worker)
        else:
            threading.Thread(target=worker, daemon=True).start()

    def _on_scan_done(self):
        # Recalculate global scan results
        sources = self.app.app_state['sources']
        total_res = {
            'total': sum(s.get('total', 0) for s in sources),
            'photos': sum(s.get('photos', 0) for s in sources),
            'videos': sum(s.get('videos', 0) for s in sources),
            'others': sum(s.get('others', 0) for s in sources),
            'size_bytes': sum(s.get('size_bytes', 0) for s in sources),
            'photos_size': sum(s.get('photos_size', 0) for s in sources),
            'videos_size': sum(s.get('videos_size', 0) for s in sources),
            'others_size': sum(s.get('others_size', 0) for s in sources),
        }
        self.app.app_state['scan_results'] = total_res
        self._refresh_list()
        
        count = total_res['total']
        self.status_lbl.configure(text=f'Total detectado: {format_count(count)} arquivos ({format_size(total_res["size_bytes"])})')

    def _remove_source(self, path):
        self.app.app_state['sources'] = [s for s in self.app.app_state['sources'] if s['path'] != path]
        self._on_scan_done()
        self._refresh_list()

    def _refresh_list(self):
        for w in self.scroll.winfo_children(): w.destroy()
        
        sources = self.app.app_state.get('sources', [])
        if not sources:
            ctk.CTkLabel(self.scroll, text='Clique em "Adicionar Pasta" para começar.', font=(FONT_FAMILY, 14), text_color=COLOR_TEXT_DIM).pack(pady=60)
            self.next_btn.configure(state='disabled')
            return
            
        self.next_btn.configure(state='normal')
        for s in sources:
            self._create_source_row(s)

    def _create_source_row(self, s):
        row = ctk.CTkFrame(self.scroll, fg_color=COLOR_BG, corner_radius=12, border_color=COLOR_BORDER, border_width=1)
        row.pack(fill='x', pady=6, padx=10)
        
        inner = ctk.CTkFrame(row, fg_color='transparent')
        inner.pack(fill='x', padx=18, pady=14)
        
        icon_lbl = ctk.CTkLabel(inner, text='📁', font=(FONT_FAMILY, 24))
        icon_lbl.pack(side='left', padx=(0, 14))
        
        info = ctk.CTkFrame(inner, fg_color='transparent')
        info.pack(side='left', fill='x', expand=True)
        
        ctk.CTkLabel(info, text=s['path'], font=(FONT_FAMILY, 14, 'bold'), text_color=COLOR_TEXT, anchor='w', wraplength=600).pack(anchor='w')
        
        if s['status'] == 'scanning':
            status_txt = 'Escaneando arquivos...'
            status_clr = COLOR_ACCENT
        elif s['status'] == 'error':
            status_txt = 'Erro ao acessar pasta'
            status_clr = COLOR_ERROR
        else:
            status_txt = f"{format_count(s['total'])} arquivos ({format_size(s['size_bytes'])}) • {format_count(s['photos'])} fotos, {format_count(s['videos'])} vídeos"
            status_clr = COLOR_TEXT_DIM
            
        ctk.CTkLabel(info, text=status_txt, font=(FONT_FAMILY, 11), text_color=status_clr, anchor='w').pack(anchor='w')
        
        ctk.CTkButton(
            inner, text='✕', font=(FONT_FAMILY, 12, 'bold'),
            fg_color='transparent', text_color=COLOR_ERROR,
            hover_color='#331111', width=32, height=32,
            command=lambda p=s['path']: self._remove_source(p)
        ).pack(side='right')

    def _continue(self):
        if self.app.app_state.get('sources'):
            self.main_window.navigate('rules')

    def refresh(self):
        self._refresh_list()
        res = self.app.app_state.get('scan_results')
        if res:
            self.status_lbl.configure(text=f'Total detectado: {format_count(res["total"])} arquivos ({format_size(res["size_bytes"])})')
