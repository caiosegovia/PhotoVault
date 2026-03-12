import threading
import time
import logging
import customtkinter as ctk
from pathlib import Path
from gui.app import (COLOR_CARD, COLOR_TEXT, COLOR_TEXT_DIM, COLOR_ACCENT,
                     COLOR_ACCENT2, COLOR_BG, COLOR_SUCCESS, COLOR_WARNING,
                     COLOR_ERROR, COLOR_BORDER, FONT_FAMILY, FONT_SIZE_TITLE, 
                     FONT_SIZE_HEADER, FONT_SIZE_BODY, FONT_SIZE_SMALL)
from utils.formatting import format_size, format_count, format_date_short

logger = logging.getLogger(__name__)

# Max photos for O(n²) visual dedup — above this, skip visual automatically
_VISUAL_CAP = 3000


class DuplicateGroupCard(ctk.CTkFrame):
    def __init__(self, parent, group_key: str, group_paths: list[Path], suggested: Path, on_decision, **kw):
        super().__init__(parent, fg_color=COLOR_CARD, corner_radius=10, **kw)
        self.group_key = group_key
        self.group_paths = group_paths
        self.suggested = suggested
        self.decision_var = ctk.StringVar(value=str(suggested))
        self._on_decision = on_decision
        self._build()

    def _build(self):
        # Header info
        header = ctk.CTkFrame(self, fg_color='transparent')
        header.pack(fill='x', padx=12, pady=(10, 0))
        
        ctk.CTkLabel(
            header, text=f"Grupo: {self.group_key[:8]}...",
            font=(FONT_FAMILY, FONT_SIZE_SMALL, 'bold'), text_color=COLOR_ACCENT2
        ).pack(side='left')

        # Thumbnails row
        thumb_row = ctk.CTkFrame(self, fg_color='transparent')
        thumb_row.pack(fill='x', padx=12, pady=(10, 10))

        for path in self.group_paths[:5]:  # show max 5
            col = ctk.CTkFrame(thumb_row, fg_color='transparent')
            col.pack(side='left', padx=6, fill='y')

            # Thumbnail
            from gui.widgets.thumbnail_viewer import ThumbnailViewer
            tv = ThumbnailViewer(col, path, size=(130, 95))
            tv.pack()

            # Metadata below thumb
            try:
                stat = path.stat()
                size_txt = format_size(stat.st_size)
            except OSError:
                size_txt = '—'

            name_lbl = ctk.CTkLabel(
                col, text=path.name,
                font=(FONT_FAMILY, 11), text_color=COLOR_TEXT,
                wraplength=130, height=32, anchor='n'
            )
            name_lbl.pack(anchor='w', pady=(4, 0))
            
            ctk.CTkLabel(
                col, text=size_txt,
                font=(FONT_FAMILY, 10), text_color=COLOR_TEXT_DIM
            ).pack(anchor='w')

            # Radio button
            is_suggested = path == self.suggested
            rb = ctk.CTkRadioButton(
                col, text='Manter' + (' ✓' if is_suggested else ''),
                variable=self.decision_var, value=str(path),
                font=(FONT_FAMILY, 11),
                text_color=COLOR_SUCCESS if is_suggested else COLOR_TEXT,
                fg_color=COLOR_ACCENT, border_color=COLOR_BORDER,
                command=lambda p=path: self._on_decision(str(p))
            )
            rb.pack(anchor='w', pady=(6, 0))

        # Action row
        action_row = ctk.CTkFrame(self, fg_color='transparent')
        action_row.pack(fill='x', padx=12, pady=(0, 10))

        ctk.CTkRadioButton(
            action_row, text='Manter todos os arquivos deste grupo',
            variable=self.decision_var, value='__all__',
            font=(FONT_FAMILY, 11), text_color=COLOR_TEXT_DIM,
            fg_color=COLOR_ACCENT, border_color=COLOR_BORDER,
            command=lambda: self._on_decision('__all__')
        ).pack(side='left')


class DuplicatesView:
    def __init__(self, parent, app, main_window):
        self.parent = parent
        self.app = app
        self.main_window = main_window
        self._scanning = False
        self._decisions: dict[str, str] = {}
        self._render_gen = 0
        self._build()

    def _build(self):
        # Main container with padding
        self.container = ctk.CTkFrame(self.parent, fg_color='transparent')
        self.container.pack(fill='both', expand=True, padx=24, pady=24)

        # Header
        header = ctk.CTkFrame(self.container, fg_color='transparent')
        header.pack(fill='x', pady=(0, 20))

        title_frame = ctk.CTkFrame(header, fg_color='transparent')
        title_frame.pack(side='left')
        
        ctk.CTkLabel(
            title_frame, text='Detecção de Duplicatas',
            font=(FONT_FAMILY, FONT_SIZE_TITLE, 'bold'), text_color=COLOR_TEXT
        ).pack(anchor='w')
        
        ctk.CTkLabel(
            title_frame, text='Identifique arquivos idênticos ou visualmente similares.',
            font=(FONT_FAMILY, FONT_SIZE_BODY), text_color=COLOR_TEXT_DIM
        ).pack(anchor='w')

        self.detect_btn = ctk.CTkButton(
            header, text='🔍  Detectar Duplicatas',
            font=(FONT_FAMILY, FONT_SIZE_BODY, 'bold'),
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT2,
            corner_radius=8, width=200, height=40,
            command=self._start_detection
        )
        self.detect_btn.pack(side='right')

        # Summary & Actions bar
        self.summary_frame = ctk.CTkFrame(self.container, fg_color=COLOR_CARD, corner_radius=12, height=60)
        self.summary_frame.pack(fill='x', pady=(0, 16))
        self.summary_frame.pack_propagate(False)

        self.summary_label = ctk.CTkLabel(
            self.summary_frame,
            text='Aguardando início da detecção...',
            font=(FONT_FAMILY, FONT_SIZE_BODY), text_color=COLOR_TEXT_DIM
        )
        self.summary_label.pack(side='left', padx=20)

        self.auto_btn = ctk.CTkButton(
            self.summary_frame, text='Aceitar Sugestões Automáticas',
            font=(FONT_FAMILY, FONT_SIZE_SMALL, 'bold'),
            fg_color=COLOR_SUCCESS, hover_color='#059669',
            corner_radius=8, width=240, height=36,
            command=self._accept_all_suggestions,
            state='disabled'
        )
        self.auto_btn.pack(side='right', padx=20)

        # Progress bar
        self.loading_bar = ctk.CTkProgressBar(
            self.container, mode='determinate', height=8, corner_radius=4,
            fg_color=COLOR_BORDER, progress_color=COLOR_ACCENT
        )

        # Tab view
        self.tabview = ctk.CTkTabview(
            self.container, fg_color=COLOR_CARD, corner_radius=12,
            segmented_button_fg_color=COLOR_BG,
            segmented_button_selected_color=COLOR_ACCENT,
            segmented_button_unselected_color=COLOR_BG,
            segmented_button_selected_hover_color=COLOR_ACCENT2
        )
        self.tabview.pack(fill='both', expand=True)

        self.tab_exact = self.tabview.add('Conteúdo Idêntico')
        self.tab_visual = self.tabview.add('Visualmente Similares')

        self.exact_scroll = ctk.CTkScrollableFrame(self.tab_exact, fg_color='transparent')
        self.exact_scroll.pack(fill='both', expand=True, padx=10, pady=10)

        self.visual_scroll = ctk.CTkScrollableFrame(self.tab_visual, fg_color='transparent')
        self.visual_scroll.pack(fill='both', expand=True, padx=10, pady=10)

        # Navigation Footer
        footer = ctk.CTkFrame(self.parent, fg_color='transparent', height=70)
        footer.pack(side='bottom', fill='x', padx=24, pady=(0, 20))

        ctk.CTkButton(
            footer, text='◀  Voltar: Preview',
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            fg_color='transparent', hover_color=COLOR_CARD,
            border_color=COLOR_BORDER, border_width=1,
            corner_radius=8, width=180, height=44,
            command=lambda: self.main_window.navigate('preview')
        ).pack(side='left')

        self.next_btn = ctk.CTkButton(
            footer, text='Próximo: Executar  ▶',
            font=(FONT_FAMILY, FONT_SIZE_BODY, 'bold'),
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT2,
            corner_radius=8, width=220, height=44,
            command=lambda: self.main_window.navigate('progress')
        )
        self.next_btn.pack(side='right')

    def _start_detection(self):
        if self._scanning:
            return
        state = self.app.app_state
        sources = state.get('sources', [])
        if not sources:
            self.summary_label.configure(text='Configure fontes antes de continuar.', text_color=COLOR_ERROR)
            return

        logger.info("Starting duplicate detection workflow")
        self._scanning = True
        self.detect_btn.configure(state='disabled')
        self.summary_label.configure(text='Iniciando varredura...', text_color=COLOR_TEXT)
        self.loading_bar.set(0)
        self.loading_bar.pack(fill='x', pady=(0, 16))
        self._clear_results()

        def worker():
            try:
                from core.scanner import scan_directory
                from core.deduplicator import find_exact_duplicates, find_visual_duplicates, DuplicateResult, suggest_keeper
                from utils.constants import PHOTO_EXTENSIONS

                all_files: list[Path] = []
                for src in sources:
                    if src.get('type') == 'cloud': continue
                    logger.debug(f"Scanning source: {src['path']}")
                    for f in scan_directory(Path(src['path'])):
                        all_files.append(f)
                        if len(all_files) % 500 == 0:
                            self.parent.after(0, lambda c=len(all_files): self.summary_label.configure(
                                text=f'Localizados {c} arquivos nas fontes...'
                            ))

                photo_files = [p for p in all_files if p.suffix.lower() in PHOTO_EXTENSIONS]
                skip_visual = len(photo_files) > _VISUAL_CAP
                
                # Execution with progress feedback
                _last_upd = [0.0]
                def on_progress(stage, cur, tot):
                    now = time.monotonic()
                    if now - _last_upd[0] < 0.1: return
                    _last_upd[0] = now
                    
                    base = 0.0 if stage == 'exact' else 0.5
                    val = base + (cur / tot if tot > 0 else 0) * 0.5
                    lbl = f"{'Exatas' if stage == 'exact' else 'Visuais'}: {cur}/{tot}"
                    self.parent.after(0, lambda v=val, l=lbl: (self.loading_bar.set(v), self.summary_label.configure(text=l)))

                dup_result = DuplicateResult()
                
                # Phase 1: Exact
                logger.info("Running exact duplicate detection")
                dup_result.exact = find_exact_duplicates(all_files, lambda c, t: on_progress('exact', c, t))
                
                for group in dup_result.exact.values():
                    try:
                        dup_result.space_wasted += sum(p.stat().st_size for p in group[1:])
                    except OSError: pass

                # Phase 2: Visual
                if skip_visual:
                    logger.warning(f"Skipping visual detection: {len(photo_files)} photos exceeds cap")
                    self.parent.after(0, lambda: self.summary_label.configure(text='Detecção visual ignorada (limite excedido).'))
                else:
                    logger.info("Running visual duplicate detection")
                    dup_result.visual = find_visual_duplicates(all_files, callback=lambda c, t: on_progress('visual', c, t))

                # Phase 3: Suggestions
                logger.info("Computing suggestions")
                suggestions = {}
                for k, paths in {**dup_result.exact, **dup_result.visual}.items():
                    suggestions[k] = suggest_keeper(paths)

                self.app.app_state['dup_result'] = dup_result
                self.app.app_state['dup_suggestions'] = suggestions
                self.parent.after(0, lambda: self._populate_results(dup_result, suggestions))
                
            except Exception as e:
                logger.exception("Error during duplicate detection")
                self.parent.after(0, lambda m=str(e): self._on_detection_error(m))

        self.app.executor.submit(worker)

    def _clear_results(self):
        self._render_gen += 1
        for w in self.exact_scroll.winfo_children(): w.destroy()
        for w in self.visual_scroll.winfo_children(): w.destroy()

    def _on_detection_error(self, msg: str):
        self._scanning = False
        self.detect_btn.configure(state='normal')
        self.loading_bar.pack_forget()
        self.summary_label.configure(text=f'Erro: {msg}', text_color=COLOR_ERROR)

    def _populate_results(self, dup_result, suggestions):
        self._scanning = False
        self.detect_btn.configure(state='normal')
        self.loading_bar.pack_forget()
        self._decisions.clear()

        total_groups = len(dup_result.exact) + len(dup_result.visual)
        self.main_window.update_dup_badge(total_groups)
        
        waste = format_size(dup_result.space_wasted)
        self.summary_label.configure(
            text=f'Encontrados {total_groups} grupos de duplicatas. Economia potencial: {waste}',
            text_color=COLOR_TEXT
        )
        self.auto_btn.configure(state='normal' if total_groups > 0 else 'disabled')

        gen = self._render_gen
        self._render_batch(list(dup_result.exact.items()), self.exact_scroll, 0, suggestions, gen=gen)
        self._render_batch(list(dup_result.visual.items()), self.visual_scroll, 0, suggestions, gen=gen)

    def _render_batch(self, items, container, start, suggestions, batch=5, gen=0):
        if gen != self._render_gen: return
        
        end = min(start + batch, len(items))
        for i in range(start, end):
            k, paths = items[i]
            card = DuplicateGroupCard(
                container, k, paths, suggestions.get(k, paths[0]),
                on_decision=lambda d, gk=k: self._record_decision(gk, d)
            )
            card.pack(fill='x', pady=8, padx=4)
            
        if end < len(items):
            self.parent.after(10, lambda: self._render_batch(items, container, end, suggestions, batch, gen))

    def _record_decision(self, group_key: str, decision: str):
        self._decisions[group_key] = decision
        logger.debug(f"Decision for {group_key}: {decision}")

    def _accept_all_suggestions(self):
        dup = self.app.app_state.get('dup_result')
        sugg = self.app.app_state.get('dup_suggestions', {})
        if not dup: return
        
        for k in {**dup.exact, **dup.visual}:
            self._decisions[k] = str(sugg.get(k))
            
        self.summary_label.configure(text='Todas as sugestões foram aceitas.', text_color=COLOR_SUCCESS)
        logger.info("User accepted all automated suggestions")

    def refresh(self):
        if self._scanning: return
        dup = self.app.app_state.get('dup_result')
        if dup:
            self._clear_results()
            self._populate_results(dup, self.app.app_state.get('dup_suggestions', {}))
