import threading
import time
import customtkinter as ctk
from pathlib import Path
from gui.app import (COLOR_CARD, COLOR_TEXT, COLOR_TEXT_DIM, COLOR_ACCENT,
                     COLOR_ACCENT2, COLOR_BG, COLOR_SUCCESS, COLOR_WARNING,
                     COLOR_ERROR, COLOR_BORDER, FONT_FAMILY, FONT_SIZE_TITLE, FONT_SIZE_HEADER,
                     FONT_SIZE_BODY, FONT_SIZE_SMALL)
from utils.formatting import format_size, format_count, format_date_short

# Max photos for O(n²) visual dedup — above this, skip visual automatically
_VISUAL_CAP = 2000


class DuplicateGroupCard(ctk.CTkFrame):
    def __init__(self, parent, group_paths: list[Path], suggested: Path, on_decision,
                 device_info: dict[str, dict] = None, **kw):
        super().__init__(parent, fg_color=COLOR_CARD, corner_radius=10, **kw)
        self.group_paths = group_paths
        self.suggested = suggested
        self.device_info = device_info or {}
        self.decision_var = ctk.StringVar(value=str(suggested))
        self._on_decision = on_decision
        self._build()

    def _build(self):
        # Thumbnails row
        thumb_row = ctk.CTkFrame(self, fg_color='transparent')
        thumb_row.pack(fill='x', padx=12, pady=(12, 4))

        for path in self.group_paths[:4]:  # show max 4
            col = ctk.CTkFrame(thumb_row, fg_color='transparent')
            col.pack(side='left', padx=6, fill='y')

            # Thumbnail
            from gui.widgets.thumbnail_viewer import ThumbnailViewer
            tv = ThumbnailViewer(col, path, size=(120, 90))
            tv.pack()

            # Metadata below thumb
            try:
                size = path.stat().st_size
                size_txt = format_size(size)
            except OSError:
                size_txt = '—'

            ctk.CTkLabel(
                col, text=path.name,
                font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=COLOR_TEXT,
                wraplength=120, anchor='w'
            ).pack(anchor='w')
            ctk.CTkLabel(
                col, text=size_txt,
                font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=COLOR_TEXT_DIM
            ).pack(anchor='w')
            origin = self.device_info.get(str(path), {})
            origin_txt = origin.get('device_name') or 'Origem desconhecida'
            origin_type = origin.get('device_type') or 'unknown'
            ctk.CTkLabel(
                col, text=f'{origin_txt} · {origin_type}',
                font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=COLOR_TEXT_DIM,
                wraplength=120, anchor='w'
            ).pack(anchor='w')

            # Radio button
            is_suggested = path == self.suggested
            rb = ctk.CTkRadioButton(
                col, text='Manter' + (' ✓' if is_suggested else ''),
                variable=self.decision_var, value=str(path),
                font=(FONT_FAMILY, FONT_SIZE_SMALL),
                text_color=COLOR_SUCCESS if is_suggested else COLOR_TEXT,
                fg_color=COLOR_ACCENT,
                command=lambda: self._on_decision(self.decision_var.get())
            )
            rb.pack(anchor='w', pady=(4, 0))

        # Keep all option
        keep_all_row = ctk.CTkFrame(self, fg_color='transparent')
        keep_all_row.pack(anchor='w', padx=12, pady=(4, 12))

        ctk.CTkRadioButton(
            keep_all_row, text='Manter todos',
            variable=self.decision_var, value='__all__',
            font=(FONT_FAMILY, FONT_SIZE_SMALL), text_color=COLOR_TEXT_DIM,
            fg_color=COLOR_ACCENT,
            command=lambda: self._on_decision('__all__')
        ).pack(side='left')


class DuplicatesView:
    def __init__(self, parent, app, main_window):
        self.parent = parent
        self.app = app
        self.main_window = main_window
        self._scanning = False
        self._decisions: dict[str, str] = {}
        self._render_gen = 0  # incremented to cancel stale batch renders
        self._build()

    def _build(self):
        # Header
        header = ctk.CTkFrame(self.parent, fg_color='transparent', height=60)
        header.pack(fill='x', padx=20, pady=(20, 0))
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text='Detecção de Duplicatas',
            font=(FONT_FAMILY, FONT_SIZE_TITLE, 'bold'), text_color=COLOR_TEXT
        ).pack(side='left', pady=10)

        ctk.CTkButton(
            header, text='Detectar Duplicatas',
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT2,
            corner_radius=8, width=180,
            command=self._start_detection
        ).pack(side='right', pady=10)

        # Summary bar
        self.summary_frame = ctk.CTkFrame(self.parent, fg_color=COLOR_CARD, corner_radius=12)
        self.summary_frame.pack(fill='x', padx=20, pady=8)

        self.summary_label = ctk.CTkLabel(
            self.summary_frame,
            text='Execute a detecção de duplicatas para visualizar resultados.',
            font=(FONT_FAMILY, FONT_SIZE_BODY), text_color=COLOR_TEXT_DIM
        )
        self.summary_label.pack(side='left', padx=20, pady=12)

        self.auto_btn = ctk.CTkButton(
            self.summary_frame, text='Aceitar sugestões automáticas',
            font=(FONT_FAMILY, FONT_SIZE_SMALL),
            fg_color=COLOR_SUCCESS, hover_color='#27ae60',
            corner_radius=6, width=220, height=32,
            command=self._accept_all_suggestions,
            state='disabled'
        )
        self.auto_btn.pack(side='right', padx=20, pady=12)

        # Loading bar (hidden initially)
        self.loading_bar = ctk.CTkProgressBar(
            self.parent, mode='determinate', height=6,
            fg_color=COLOR_BORDER, progress_color=COLOR_ACCENT
        )

        # Tab view
        self.tabview = ctk.CTkTabview(
            self.parent, fg_color=COLOR_CARD, corner_radius=12,
            segmented_button_fg_color=COLOR_CARD,
            segmented_button_selected_color=COLOR_ACCENT,
            segmented_button_unselected_color=COLOR_CARD
        )
        self.tabview.pack(fill='both', expand=True, padx=20, pady=(0, 8))

        self.tab_exact = self.tabview.add('Exatas (SHA-256)')
        self.tab_visual = self.tabview.add('Visuais (pHash)')

        self.exact_scroll = ctk.CTkScrollableFrame(self.tab_exact, fg_color='transparent')
        self.exact_scroll.pack(fill='both', expand=True)

        self.visual_scroll = ctk.CTkScrollableFrame(self.tab_visual, fg_color='transparent')
        self.visual_scroll.pack(fill='both', expand=True)

        # Navigation
        nav = ctk.CTkFrame(self.parent, fg_color='transparent')
        nav.pack(fill='x', padx=20, pady=(0, 16))

        ctk.CTkButton(
            nav, text='← Voltar',
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            fg_color='transparent', hover_color=COLOR_ACCENT,
            border_color=COLOR_ACCENT, border_width=1,
            corner_radius=8, width=120, height=40,
            command=lambda: self.main_window.navigate('preview')
        ).pack(side='left')

        ctk.CTkButton(
            nav, text='Continuar → Executar',
            font=(FONT_FAMILY, FONT_SIZE_BODY, 'bold'),
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT2,
            corner_radius=8, width=200, height=40,
            command=self._continue
        ).pack(side='right')

    def _start_detection(self):
        if self._scanning:
            return
        sources = self.app.app_state.get('sources', [])
        destination = self.app.app_state.get('destination')
        if not sources and not destination:
            self.summary_label.configure(text='Adicione fontes ou selecione um destino antes de detectar duplicatas.')
            return

        self._scanning = True
        self.summary_label.configure(text='Detectando duplicatas em origens e destino...')
        self.loading_bar.set(0)
        self.loading_bar.pack(fill='x', padx=20, pady=(0, 4))
        self._clear_results()  # also increments _render_gen

        EXACT_END = 0.70

        def worker():
            try:
                from core.scanner import scan_directory
                from core.deduplicator import (find_exact_duplicates,
                                               find_visual_duplicates,
                                               DuplicateResult, suggest_keeper)
                from utils.constants import PHOTO_EXTENSIONS

                # --- Fase 0: varredura de fontes (com feedback por contagem) ---
                all_files: list[Path] = []
                scan_sources = []
                seen_roots = set()
                for src in sources:
                    if src.get('type') == 'cloud':
                        continue
                    root = Path(src['path'])
                    key = str(root.resolve()).lower() if root.exists() else str(root).lower()
                    if key in seen_roots:
                        continue
                    seen_roots.add(key)
                    scan_sources.append({'path': root, 'role': 'origin'})

                destination = self.app.app_state.get('destination')
                if destination:
                    dest = Path(destination)
                    key = str(dest.resolve()).lower() if dest.exists() else str(dest).lower()
                    if dest.exists() and key not in seen_roots:
                        seen_roots.add(key)
                        scan_sources.append({'path': dest, 'role': 'destination'})

                for src in scan_sources:
                    root = src['path']
                    label = 'destino' if src.get('role') == 'destination' else 'fontes'
                    for f in scan_directory(root):
                        all_files.append(f)
                        n = len(all_files)
                        if n % 200 == 0:
                            self.parent.after(0, lambda c=n, lbl=label: self.summary_label.configure(
                                text=f'Escaneando {lbl}: {c} arquivos encontrados...'
                            ))

                threshold = self.app.app_state.get('phash_threshold', 10)
                photo_files = [p for p in all_files if p.suffix.lower() in PHOTO_EXTENSIONS]
                skip_visual = len(photo_files) > _VISUAL_CAP

                # Time-based throttle — max ~10 UI updates/sec regardless of file count
                _last_upd = [0.0]

                def on_progress(stage, cur, tot):
                    if tot == 0:
                        return
                    now = time.monotonic()
                    if now - _last_upd[0] < 0.10:
                        return
                    _last_upd[0] = now
                    if stage == 'exact':
                        val = (cur / tot) * EXACT_END
                        lbl = f'Duplicatas exatas: {cur}/{tot} ({int(cur / tot * 100)}%)'
                    else:
                        val = EXACT_END + (cur / tot) * (1 - EXACT_END)
                        lbl = f'Duplicatas visuais: {cur}/{tot} ({int(cur / tot * 100)}%)'
                    self.parent.after(0, lambda v=val, l=lbl: (
                        self.loading_bar.set(v),
                        self.summary_label.configure(text=l)
                    ))

                dup_result = DuplicateResult()

                # --- Fase 1: duplicatas exatas ---
                # Fase 1a (agrupamento por tamanho) tem callback normal.
                # Fases 1b/1c (partial+full hash) não têm callback → bar parece travar.
                # Solução: ao detectar fim da fase 1a, ligar modo indeterminate.
                _hash_phase_started = [False]

                def exact_cb(cur, tot):
                    on_progress('exact', cur, tot)
                    if not _hash_phase_started[0] and tot > 0 and cur >= tot - 1:
                        _hash_phase_started[0] = True
                        def _start_indet():
                            self.loading_bar.configure(mode='indeterminate')
                            self.loading_bar.start()
                            self.summary_label.configure(text='Calculando hashes SHA-256...')
                        self.parent.after(0, _start_indet)

                dup_result.exact = find_exact_duplicates(all_files, exact_cb)

                # Restaurar barra após fase exata
                def _stop_indet():
                    self.loading_bar.stop()
                    self.loading_bar.configure(mode='determinate')
                    self.loading_bar.set(EXACT_END)
                self.parent.after(0, _stop_indet)

                for group in dup_result.exact.values():
                    if len(group) > 1:
                        try:
                            for dup in group[1:]:
                                dup_result.space_wasted += dup.stat().st_size
                        except OSError:
                            pass

                # --- Fase 2: duplicatas visuais ---
                if skip_visual:
                    n = len(photo_files)
                    self.parent.after(0, lambda: self.summary_label.configure(
                        text=f'Detecção visual ignorada — {n} fotos excedem o limite de {_VISUAL_CAP}.'
                    ))
                else:
                    def visual_cb(cur, tot): on_progress('visual', cur, tot)
                    try:
                        dup_result.visual = find_visual_duplicates(
                            all_files, threshold=threshold, callback=visual_cb
                        )
                    except Exception:
                        dup_result.visual = {}

                # Pre-compute suggestions in worker (avoids EXIF reads on main thread)
                suggestions: dict[str, Path] = {}
                device_info: dict[str, dict] = {}
                from core.metadata import get_media_info
                for k, paths in list(dup_result.exact.items()) + list(dup_result.visual.items()):
                    suggestions[k] = suggest_keeper(paths)
                    for path in paths:
                        key = str(path)
                        if key in device_info:
                            continue
                        try:
                            info = get_media_info(path)
                            device_info[key] = {
                                'device_name': info.get('device_name') or 'Desconhecido',
                                'device_type': info.get('device_type') or 'unknown',
                            }
                        except Exception:
                            device_info[key] = {
                                'device_name': 'Desconhecido',
                                'device_type': 'unknown',
                            }

                self.app.app_state['dup_result'] = dup_result
                self.app.app_state['dup_suggestions'] = suggestions
                self.app.app_state['dup_device_info'] = device_info
                self.parent.after(0, lambda: self._populate_results(dup_result, suggestions, device_info))
            except Exception as e:
                self.parent.after(0, lambda msg=str(e): self._on_detection_error(msg))

        threading.Thread(target=worker, daemon=True).start()

    def _clear_results(self):
        self._render_gen += 1  # cancels any pending _render_batch callbacks
        for w in self.exact_scroll.winfo_children():
            w.destroy()
        for w in self.visual_scroll.winfo_children():
            w.destroy()

    def _on_detection_error(self, msg: str):
        self._scanning = False
        self.loading_bar.pack_forget()
        self.summary_label.configure(
            text=f'Erro na detecção: {msg}', text_color=COLOR_ERROR
        )

    def _populate_results(self, dup_result, suggestions: dict = None, device_info: dict = None):
        self._scanning = False
        self.loading_bar.set(1.0)
        self.loading_bar.pack_forget()
        self._decisions.clear()

        if suggestions is None:
            suggestions = {}
        if device_info is None:
            device_info = {}

        exact_count = len(dup_result.exact)
        visual_count = len(dup_result.visual)
        total_groups = exact_count + visual_count

        self.main_window.update_dup_badge(total_groups)

        dup_files = sum(len(g) for g in dup_result.exact.values()) + \
                    sum(len(g) for g in dup_result.visual.values())

        self._summary_text = (
            f'{total_groups} grupos  •  {dup_files} arquivos  •  '
            f'{format_size(dup_result.space_wasted)} liberáveis'
        )
        self.summary_label.configure(text=self._summary_text)
        self.auto_btn.configure(state='normal')

        exact_items = list(dup_result.exact.items())
        visual_items = list(dup_result.visual.items())

        if not exact_items:
            ctk.CTkLabel(
                self.exact_scroll, text='Nenhuma duplicata exata encontrada.',
                text_color=COLOR_TEXT_DIM, font=(FONT_FAMILY, FONT_SIZE_BODY)
            ).pack(pady=30)

        if not visual_items:
            ctk.CTkLabel(
                self.visual_scroll, text='Nenhuma duplicata visual encontrada.',
                text_color=COLOR_TEXT_DIM, font=(FONT_FAMILY, FONT_SIZE_BODY)
            ).pack(pady=30)

        gen = self._render_gen
        self._render_batch(exact_items, self.exact_scroll, 0, suggestions, device_info, gen=gen)
        self._render_batch(visual_items, self.visual_scroll, 0, suggestions, device_info, gen=gen)

    def _render_batch(self, items, container, start, suggestions: dict, device_info: dict,
                      batch=4, gen=0):
        """Render `batch` cards then yield to the event loop — keeps UI responsive."""
        if gen != self._render_gen:
            return  # cancelled — navigated away or new detection started
        end = min(start + batch, len(items))
        for i in range(start, end):
            hash_key, paths = items[i]
            suggested = suggestions.get(hash_key, paths[0])
            card = DuplicateGroupCard(
                container, paths, suggested,
                on_decision=lambda d, k=hash_key: self._record_decision(k, d),
                device_info=device_info,
            )
            card.pack(fill='x', pady=6, padx=4)
        if end < len(items):
            self.parent.after(50, lambda s=end: self._render_batch(
                items, container, s, suggestions, device_info, batch, gen
            ))

    def _record_decision(self, group_key: str, decision: str):
        self._decisions[group_key] = decision

    def _accept_all_suggestions(self):
        dup = self.app.app_state.get('dup_result')
        if not dup:
            return
        from core.deduplicator import suggest_keeper
        for k, paths in dup.exact.items():
            self._decisions[k] = str(suggest_keeper(paths))
        for k, paths in dup.visual.items():
            self._decisions[k] = str(suggest_keeper(paths))
        self.summary_label.configure(text='Sugestões automáticas aplicadas.')

    def _continue(self):
        self._apply_decisions_to_plan()
        self.main_window.navigate('progress')

    def _apply_decisions_to_plan(self):
        plan = self.app.app_state.get('plan')
        dup = self.app.app_state.get('dup_result')
        if not plan or not dup or not self._decisions:
            return

        groups = {}
        groups.update(dup.exact)
        groups.update(dup.visual)
        from core.organizer import apply_duplicate_decisions
        apply_duplicate_decisions(plan, groups, self._decisions)

    def refresh(self):
        dup = self.app.app_state.get('dup_result')
        if dup:
            self._clear_results()
            suggestions = self.app.app_state.get('dup_suggestions', {})
            device_info = self.app.app_state.get('dup_device_info', {})
            self._populate_results(dup, suggestions, device_info)
