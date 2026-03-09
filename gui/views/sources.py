import threading
import customtkinter as ctk
from pathlib import Path
from tkinter import filedialog
from gui.app import (COLOR_CARD, COLOR_TEXT, COLOR_TEXT_DIM, COLOR_ACCENT,
                     COLOR_ACCENT2, COLOR_BG, COLOR_SUCCESS, COLOR_WARNING,
                     COLOR_ERROR, FONT_FAMILY, FONT_SIZE_TITLE, FONT_SIZE_HEADER,
                     FONT_SIZE_BODY, FONT_SIZE_SMALL)
from utils.formatting import format_size, format_count


class SourcesView:
    def __init__(self, parent, app, main_window):
        self.parent = parent
        self.app = app
        self.main_window = main_window
        self._scanning = False
        self._build()

    def _build(self):
        self.scroll = ctk.CTkScrollableFrame(self.parent, fg_color='transparent')
        self.scroll.pack(fill='both', expand=True, padx=20, pady=20)

        # Header
        header = ctk.CTkFrame(self.scroll, fg_color='transparent')
        header.pack(fill='x', pady=(0, 20))
        ctk.CTkLabel(
            header, text='Fontes de Mídia',
            font=(FONT_FAMILY, FONT_SIZE_TITLE, 'bold'), text_color=COLOR_TEXT
        ).pack(side='left')

        # Action buttons
        btn_frame = ctk.CTkFrame(self.scroll, fg_color=COLOR_CARD, corner_radius=12)
        btn_frame.pack(fill='x', pady=(0, 16))

        inner = ctk.CTkFrame(btn_frame, fg_color='transparent')
        inner.pack(padx=20, pady=16)

        ctk.CTkButton(
            inner, text='+ Adicionar Pasta',
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT2,
            corner_radius=8, width=160, command=self._add_folder
        ).pack(side='left', padx=(0, 12))

        ctk.CTkButton(
            inner, text='⬡ Detectar Drives',
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            fg_color='transparent', hover_color=COLOR_ACCENT,
            border_color=COLOR_ACCENT, border_width=1,
            corner_radius=8, width=160, command=self._detect_drives
        ).pack(side='left', padx=(0, 12))

        ctk.CTkButton(
            inner, text='☁ Google Photos',
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            fg_color='transparent', hover_color=COLOR_ACCENT,
            border_color=COLOR_ACCENT, border_width=1,
            corner_radius=8, width=160, command=self._add_google_photos
        ).pack(side='left')

        # Sources list
        ctk.CTkLabel(
            self.scroll, text='Fontes Adicionadas',
            font=(FONT_FAMILY, FONT_SIZE_HEADER, 'bold'), text_color=COLOR_TEXT
        ).pack(anchor='w', pady=(10, 8))

        self.sources_list = ctk.CTkFrame(self.scroll, fg_color='transparent')
        self.sources_list.pack(fill='x')

        # Status + scan button
        self.status_label = ctk.CTkLabel(
            self.scroll, text='',
            font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=COLOR_TEXT_DIM
        )
        self.status_label.pack(pady=8)

        self.loading_bar = ctk.CTkProgressBar(
            self.scroll, mode='indeterminate', height=6,
            fg_color='#2a2a4a', progress_color=COLOR_ACCENT
        )

        self.scan_btn = ctk.CTkButton(
            self.scroll, text='Próximo: Regras  ▶',
            font=(FONT_FAMILY, FONT_SIZE_BODY, 'bold'),
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT2,
            corner_radius=8, height=44, width=220,
            command=self._start_scan
        )
        self.scan_btn.pack(pady=10)

        self._refresh_sources()

    def _refresh_sources(self):
        for w in self.sources_list.winfo_children():
            w.destroy()
        sources = self.app.app_state.get('sources', [])
        if not sources:
            ctk.CTkLabel(
                self.sources_list, text='Nenhuma fonte adicionada ainda.',
                text_color=COLOR_TEXT_DIM, font=(FONT_FAMILY, FONT_SIZE_BODY)
            ).pack(pady=20)
            return
        for src in sources:
            self._create_source_card(src)

    def _create_source_card(self, src: dict):
        card = ctk.CTkFrame(self.sources_list, fg_color=COLOR_CARD, corner_radius=10)
        card.pack(fill='x', pady=4)

        inner = ctk.CTkFrame(card, fg_color='transparent')
        inner.pack(fill='x', padx=16, pady=12)

        icon = '📁' if src.get('type') == 'local' else ('💾' if src.get('type') == 'drive' else '☁')
        ctk.CTkLabel(inner, text=icon, font=(FONT_FAMILY, 20)).pack(side='left', padx=(0, 12))

        info = ctk.CTkFrame(inner, fg_color='transparent')
        info.pack(side='left', fill='x', expand=True)
        ctk.CTkLabel(
            info, text=str(src.get('path', '')),
            font=(FONT_FAMILY, FONT_SIZE_BODY), text_color=COLOR_TEXT, anchor='w'
        ).pack(anchor='w')

        details = f"{format_count(src.get('total', 0))} arquivos"
        if src.get('size_bytes'):
            details += f"  •  {format_size(src['size_bytes'])}"
        ctk.CTkLabel(
            info, text=details,
            font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=COLOR_TEXT_DIM, anchor='w'
        ).pack(anchor='w')

        ctk.CTkButton(
            inner, text='✕', width=30, height=30,
            fg_color='transparent', hover_color=COLOR_ERROR,
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            command=lambda s=src: self._remove_source(s)
        ).pack(side='right')

    def _add_folder(self):
        path = filedialog.askdirectory(title='Selecionar pasta de fotos/vídeos')
        if not path:
            return
        p = Path(path)
        self._count_and_add(p, 'local')

    def _count_and_add(self, path: Path, src_type: str):
        self.status_label.configure(text='Contando arquivos...')
        self.loading_bar.configure(mode='indeterminate')
        self.loading_bar.pack(fill='x', padx=20, pady=(0, 4))
        self.loading_bar.start()

        def worker():
            from core.scanner import count_files
            counts = count_files(path)
            src = {
                'path': str(path),
                'type': src_type,
                **counts
            }
            self.app.app_state['sources'].append(src)
            self.parent.after(0, self._on_source_added)

        threading.Thread(target=worker, daemon=True).start()

    def _on_source_added(self):
        self.loading_bar.stop()
        self.loading_bar.pack_forget()
        self.status_label.configure(text='')
        self._refresh_sources()

    def _remove_source(self, src: dict):
        self.app.app_state['sources'] = [
            s for s in self.app.app_state['sources'] if s['path'] != src['path']
        ]
        self._refresh_sources()

    def _detect_drives(self):
        from core.scanner import detect_drives
        drives = detect_drives()
        if not drives:
            self.status_label.configure(text='Nenhum drive externo encontrado.')
            return
        # Show selection dialog
        self._show_drive_dialog(drives)

    def _show_drive_dialog(self, drives: list):
        win = ctk.CTkToplevel(self.parent)
        win.title('Selecionar Drive')
        win.geometry('500x400')
        win.configure(fg_color=COLOR_BG)

        ctk.CTkLabel(
            win, text='Drives Detectados',
            font=(FONT_FAMILY, FONT_SIZE_HEADER, 'bold'), text_color=COLOR_TEXT
        ).pack(pady=20)

        scroll = ctk.CTkScrollableFrame(win, fg_color='transparent')
        scroll.pack(fill='both', expand=True, padx=20)

        for drive in drives:
            btn = ctk.CTkButton(
                scroll,
                text=f"  {drive['label']}  —  {format_size(drive.get('total_space', 0))}",
                anchor='w', fg_color=COLOR_CARD, hover_color=COLOR_ACCENT,
                corner_radius=8, height=44, font=(FONT_FAMILY, FONT_SIZE_BODY),
                command=lambda d=drive, w=win: self._select_drive(d, w)
            )
            btn.pack(fill='x', pady=4)

    def _select_drive(self, drive: dict, win):
        win.destroy()
        self._count_and_add(Path(drive['path']), 'drive')

    def _add_google_photos(self):
        try:
            from integrations.google_photos import GooglePhotosClient
            from utils.constants import CONFIG_DIR, TOKEN_PATH

            # Reuse already-authenticated client from settings if available
            client = self.app.app_state.get('google_client')
            if client is None:
                creds_path = CONFIG_DIR / 'google_client_secret.json'
                assets_path = Path('assets') / 'google_client_secret.json'
                if not creds_path.exists() and assets_path.exists():
                    creds_path = assets_path
                if not creds_path.exists() and not TOKEN_PATH.exists():
                    self.status_label.configure(
                        text='Configure as credenciais Google em Configurações primeiro.')
                    return
                client = GooglePhotosClient(str(creds_path))

            self.status_label.configure(text='Autenticando no Google...')
            if client.authenticate():
                self.app.app_state['google_client'] = client
                quota = client.get_storage_quota()

                # We need to scan/count cloud items too
                self.status_label.configure(text='Sincronizando metadados do Google Photos...')
                self.loading_bar.configure(mode='indeterminate')
                self.loading_bar.pack(fill='x', padx=20, pady=(0, 4))
                self.loading_bar.start()

                def cloud_worker():
                    items = []
                    def cb(count):
                        self.parent.after(0, lambda c=count: self.status_label.configure(
                            text=f'Sincronizando Google Photos: {c} itens...'))

                    for item in client.list_media_items(callback=cb):
                        items.append(item)

                    src = {
                        'path': 'Google Photos',
                        'type': 'cloud',
                        'client': client,
                        'items': items,
                        'size_bytes': quota.get('used', 0),
                        'total': len(items),
                        'photos': sum(1 for i in items if 'image' in i.get('mimeType', '')),
                        'videos': sum(1 for i in items if 'video' in i.get('mimeType', '')),
                    }
                    self.parent.after(0, lambda s=src: self._on_cloud_added(s))

                threading.Thread(target=cloud_worker, daemon=True).start()
            else:
                self.status_label.configure(text='Falha na autenticação. Verifique em Configurações.')
        except Exception as e:
            self.status_label.configure(text=f'Erro: {e}')

    def _on_cloud_added(self, src):
        self.loading_bar.stop()
        self.loading_bar.pack_forget()
        self.app.app_state['sources'].append(src)
        self._refresh_sources()
        self.status_label.configure(text='Google Photos conectado e sincronizado!')

    def _start_scan(self):
        sources = self.app.app_state.get('sources', [])
        if not sources:
            self.status_label.configure(text='Adicione ao menos uma fonte antes de escanear.')
            return

        self._scanning = True
        self.scan_btn.configure(state='disabled', text='Escaneando...')
        self.status_label.configure(text='Escaneando...')
        self.loading_bar.configure(mode='determinate')
        self.loading_bar.set(0)
        self.loading_bar.pack(fill='x', padx=20, pady=(0, 4))

        def worker():
            from core.scanner import count_files
            local_srcs = [s for s in sources if s.get('type') != 'cloud']
            cloud_srcs = [s for s in sources if s.get('type') == 'cloud']
            n = len(local_srcs) + len(cloud_srcs)
            totals = {
                'total': 0, 'photos': 0, 'videos': 0, 'others': 0, 'size_bytes': 0,
                'photos_size': 0, 'videos_size': 0, 'others_size': 0
            }

            # Local scan
            for i, src in enumerate(local_srcs):
                counts = count_files(Path(src['path']))
                for k in totals:
                    totals[k] += counts.get(k, 0)
                val = (i + 1) / max(n, 1)
                idx = i + 1
                self.parent.after(0, lambda v=val, ix=idx, t=n: (
                    self.loading_bar.set(v),
                    self.status_label.configure(text=f'Pasta {ix} de {t}...')
                ))
            # Cloud items contribution
            for src in cloud_srcs:
                for k in ['total', 'photos', 'videos', 'others', 'size_bytes']:
                    totals[k] += src.get(k, 0)
                # Google doesn't give size per type easily in quota, so we estimate or just add to total
                totals['photos_size'] += src.get('size_bytes', 0) if src.get('photos', 0) > 0 else 0

            self.app.app_state['scan_results'] = totals
            self.parent.after(0, self._on_scan_done)

        threading.Thread(target=worker, daemon=True).start()

    def _on_scan_done(self):
        self._scanning = False
        self.loading_bar.pack_forget()
        self.scan_btn.configure(state='normal', text='Próximo: Regras  ▶')
        results = self.app.app_state.get('scan_results', {})
        total = results.get('total', 0)
        self.status_label.configure(
            text=f'Scan concluído: {format_count(total)} arquivos encontrados.'
        )
        self.main_window.navigate('rules')

    def refresh(self):
        self._refresh_sources()
