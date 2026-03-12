import threading
import logging
import time
from pathlib import Path
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
from gui.app import (COLOR_CARD, COLOR_TEXT, COLOR_TEXT_DIM, COLOR_ACCENT,
                     COLOR_ACCENT2, COLOR_BG, COLOR_SUCCESS, COLOR_WARNING,
                     COLOR_BORDER, COLOR_ERROR, FONT_FAMILY, FONT_SIZE_TITLE,
                     FONT_SIZE_HEADER, FONT_SIZE_BODY, FONT_SIZE_SMALL)
from utils.formatting import format_size, format_count

logger = logging.getLogger(__name__)

class PreviewView:
    def __init__(self, parent, app, main_window):
        self.parent = parent
        self.app = app
        self.main_window = main_window
        self._planning = False
        self._render_gen = 0
        self._build()

    def _build(self):
        # Header
        header = ctk.CTkFrame(self.parent, fg_color='transparent')
        header.pack(fill='x', padx=30, pady=(30, 0))

        title_frame = ctk.CTkFrame(header, fg_color='transparent')
        title_frame.pack(side='left')
        
        ctk.CTkLabel(
            title_frame, text='Preview da Organização',
            font=(FONT_FAMILY, FONT_SIZE_TITLE, 'bold'), text_color=COLOR_TEXT
        ).pack(anchor='w')
        
        ctk.CTkLabel(
            title_frame, text='Verifique como seus arquivos serão organizados no destino.',
            font=(FONT_FAMILY, FONT_SIZE_BODY), text_color=COLOR_TEXT_DIM
        ).pack(anchor='w')

        self.gen_btn = ctk.CTkButton(
            header, text='⚡ Gerar Preview',
            font=(FONT_FAMILY, FONT_SIZE_BODY, 'bold'),
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT2,
            corner_radius=10, width=180, height=44,
            command=self._generate_plan
        )
        self.gen_btn.pack(side='right')

        # Loading bar (hidden initially)
        self.loading_bar = ctk.CTkProgressBar(
            self.parent, mode='determinate', height=8, corner_radius=4,
            fg_color=COLOR_BORDER, progress_color=COLOR_ACCENT
        )

        # Tab view for Tree vs Grid
        self.tabview = ctk.CTkTabview(
            self.parent, fg_color=COLOR_CARD, corner_radius=16,
            segmented_button_fg_color=COLOR_BG,
            segmented_button_selected_color=COLOR_ACCENT,
            segmented_button_unselected_color=COLOR_BG
        )
        self.tabview.pack(fill='both', expand=True, padx=30, pady=20)

        self.tab_tree = self.tabview.add('Lista Estruturada')
        self.tab_grid = self.tabview.add('Galeria de Miniaturas')

        # Style treeview for dark theme
        style = ttk.Style()
        style.theme_use('clam')
        style.configure(
            'PhotoVault.Treeview',
            background='#161826', foreground=COLOR_TEXT,
            fieldbackground='#161826', borderwidth=0,
            font=(FONT_FAMILY, 11), rowheight=30
        )
        style.configure(
            'PhotoVault.Treeview.Heading',
            background=COLOR_CARD, foreground=COLOR_TEXT_DIM,
            font=(FONT_FAMILY, 11, 'bold'), borderwidth=0
        )
        style.map('PhotoVault.Treeview', background=[('selected', COLOR_ACCENT)])

        tree_frame = ctk.CTkFrame(self.tab_tree, fg_color='transparent')
        tree_frame.pack(fill='both', expand=True, padx=10, pady=10)

        self.tree = ttk.Treeview(
            tree_frame, style='PhotoVault.Treeview',
            columns=('count', 'size', 'status'), show='tree headings'
        )
        self.tree.heading('#0', text='Estrutura de Destino')
        self.tree.heading('count', text='Itens')
        self.tree.heading('size', text='Tamanho')
        self.tree.heading('status', text='Status')
        self.tree.column('#0', width=500)
        self.tree.column('count', width=100, anchor='center')
        self.tree.column('size', width=120, anchor='e')
        self.tree.column('status', width=120, anchor='center')

        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        # Grid view
        self.grid_scroll = ctk.CTkScrollableFrame(self.tab_grid, fg_color='transparent')
        self.grid_scroll.pack(fill='both', expand=True, padx=10, pady=10)
        self._grid_cols = 6
        for i in range(self._grid_cols): self.grid_scroll.columnconfigure(i, weight=1)

        # Tag colors
        self.tree.tag_configure('new', foreground=COLOR_SUCCESS)
        self.tree.tag_configure('conflict', foreground=COLOR_WARNING)
        self.tree.tag_configure('exists', foreground=COLOR_TEXT_DIM)
        self.tree.tag_configure('folder', foreground=COLOR_ACCENT2)

        # Summary Bar
        summary_frame = ctk.CTkFrame(self.parent, fg_color=COLOR_CARD, corner_radius=12, height=50)
        summary_frame.pack(fill='x', padx=30, pady=(0, 20))
        summary_frame.pack_propagate(False)

        self.summary_label = ctk.CTkLabel(
            summary_frame, text='Gere um preview para ver os resultados.',
            font=(FONT_FAMILY, FONT_SIZE_BODY), text_color=COLOR_TEXT_DIM
        )
        self.summary_label.pack(side='left', padx=20)

        # Legend
        legend = ctk.CTkFrame(summary_frame, fg_color='transparent')
        legend.pack(side='right', padx=20)
        for label, color in [('Novo', COLOR_SUCCESS), ('Conflito', COLOR_WARNING), ('Existente', COLOR_TEXT_DIM)]:
            ctk.CTkLabel(legend, text=f'● {label}', font=(FONT_FAMILY, 11), text_color=color).pack(side='left', padx=10)

        # Nav Buttons
        nav_frame = ctk.CTkFrame(self.parent, fg_color='transparent', height=70)
        nav_frame.pack(side='bottom', fill='x', padx=30, pady=(0, 20))

        ctk.CTkButton(
            nav_frame, text='◀  Voltar: Regras',
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            fg_color='transparent', border_color=COLOR_BORDER, border_width=1,
            corner_radius=10, width=180, height=44,
            command=lambda: self.main_window.navigate('rules')
        ).pack(side='left')

        self.next_btn = ctk.CTkButton(
            nav_frame, text='Próximo: Duplicatas  ▶',
            font=(FONT_FAMILY, FONT_SIZE_BODY, 'bold'),
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT2,
            corner_radius=10, width=220, height=44,
            command=self._continue
        )
        self.next_btn.pack(side='right')

    def _generate_plan(self):
        if self._planning: return
        state = self.app.app_state
        sources = [s for s in state.get('sources', []) if s.get('type') != 'cloud']
        destination = state.get('destination')
        
        if not sources or not destination:
            self.summary_label.configure(text='Erro: Fontes ou destino não configurados.', text_color=COLOR_ERROR)
            return

        logger.info("Starting organization planning")
        self._planning = True
        self.gen_btn.configure(state='disabled')
        self.summary_label.configure(text='Calculando estrutura de arquivos...', text_color=COLOR_TEXT)
        self.loading_bar.set(0)
        self.loading_bar.pack(fill='x', padx=30, pady=(0, 10))
        self._clear_views()

        def worker():
            try:
                from core.organizer import plan_organization
                from core.scanner import count_files
                
                logger.debug("Counting source files")
                pre_total = sum(count_files(Path(s['path'])).get('total', 0) for s in sources)
                
                _last_upd = [0.0]
                def cb(file, done):
                    now = time.monotonic()
                    if now - _last_upd[0] < 0.1: return
                    _last_upd[0] = now
                    val = done / pre_total if pre_total > 0 else 0
                    self.parent.after(0, lambda v=val, d=done, t=pre_total: (
                        self.loading_bar.set(v),
                        self.summary_label.configure(text=f'Gerando plano... {d}/{t} arquivos')
                    ))

                plan = plan_organization(
                    sources=[Path(s['path']) for s in sources],
                    destination=destination,
                    pattern=state.get('pattern', '{year}/{month:02d}'),
                    mode=state.get('mode', 'copy'),
                    include_no_date=state.get('include_no_date', True),
                    skip_existing=state.get('skip_existing', True),
                    callback=cb,
                )
                
                self.app.app_state['plan'] = plan
                self.parent.after(0, lambda: self._populate_ui(plan))
            except Exception as e:
                logger.exception("Error during organization planning")
                self.parent.after(0, lambda m=str(e): self._on_error(m))

        self.app.executor.submit(worker)

    def _clear_views(self):
        self._render_gen += 1
        for item in self.tree.get_children(): self.tree.delete(item)
        for w in self.grid_scroll.winfo_children(): w.destroy()

    def _on_error(self, msg):
        self._planning = False
        self.gen_btn.configure(state='normal')
        self.loading_bar.pack_forget()
        self.summary_label.configure(text=f'Erro: {msg}', text_color=COLOR_ERROR)

    def _populate_ui(self, plan):
        self._planning = False
        self.gen_btn.configure(state='normal')
        self.loading_bar.pack_forget()
        
        logger.info(f"Plan generated: {len(plan.operations)} operations")
        
        # We'll populate tree in batches to avoid freezing
        ops = plan.operations
        self._populate_tree_batch(ops, 0, plan.destination, {}, gen=self._render_gen)
        self._render_grid_batch(ops, 0, gen=self._render_gen)

    def _populate_tree_batch(self, ops, start, base_dest, folders, batch=100, gen=0):
        if gen != self._render_gen: return
        
        end = min(start + batch, len(ops))
        for i in range(start, end):
            op = ops[i]
            try:
                rel = op.dst.relative_to(base_dest)
                parts = rel.parts
            except ValueError:
                parts = (op.dst.name,)
            
            parent = ''
            for j, part in enumerate(parts[:-1]):
                key = '/'.join(parts[:j+1])
                if key not in folders:
                    iid = self.tree.insert(parent, 'end', iid=key, text=f'📁 {part}', tags=('folder',), open=j<1)
                    folders[key] = {'iid': iid, 'count': 0, 'size': 0}
                parent = key
                folders[key]['count'] += 1
                # Try to get size from op (cached if possible)
                sz = getattr(op, '_size_cache', None)
                if sz is None:
                    try:
                        sz = op.src.stat().st_size
                        op._size_cache = sz
                    except OSError: sz = 0
                folders[key]['size'] += sz

            # Insert file
            status = 'new'
            status_txt = 'Novo'
            if op.dst.exists():
                status = 'conflict'
                status_txt = 'Conflito'
            elif op.action == 'skip':
                status = 'exists'
                status_txt = 'Já existe'
                
            sz = getattr(op, '_size_cache', 0)
            self.tree.insert(parent, 'end', text=f'  📄 {op.src.name}', 
                             values=('—', format_size(sz), status_txt), tags=(status,))

        # Update folder stats in tree
        if end % 500 == 0 or end == len(ops):
            for key, data in folders.items():
                self.tree.item(data['iid'], values=(data['count'], format_size(data['size']), ''))

        if end < len(ops):
            self.parent.after(1, lambda: self._populate_tree_batch(ops, end, base_dest, folders, batch, gen))
        else:
            conflicts = sum(1 for op in ops if op.dst.exists())
            self.summary_label.configure(text=f'Preview concluído: {format_count(len(ops))} arquivos. Conflitos detectados: {conflicts}')

    def _render_grid_batch(self, ops, start, batch=12, gen=0):
        if gen != self._render_gen: return
        
        # Only render first 300 items in grid for performance
        MAX_GRID = 300
        end = min(start + batch, len(ops), MAX_GRID)
        
        from gui.widgets.thumbnail_viewer import ThumbnailViewer
        for i in range(start, end):
            op = ops[i]
            r, c = divmod(i, self._grid_cols)
            frame = ctk.CTkFrame(self.grid_scroll, fg_color='transparent')
            frame.grid(row=r, column=c, padx=8, pady=8, sticky='nsew')
            
            ThumbnailViewer(frame, op.src, size=(140, 105)).pack()
            ctk.CTkLabel(frame, text=op.src.name, font=(FONT_FAMILY, 10), text_color=COLOR_TEXT_DIM, wraplength=130).pack(pady=4)

        if end < len(ops) and end < MAX_GRID:
            self.parent.after(5, lambda: self._render_grid_batch(ops, end, batch, gen))

    def _continue(self):
        if self.app.app_state.get('plan'):
            self.main_window.navigate('duplicates')
        else:
            self._generate_plan()

    def refresh(self):
        if not self.app.app_state.get('plan'):
            self._clear_views()
            self.summary_label.configure(text='Gere um preview para ver os resultados.', text_color=COLOR_TEXT_DIM)
            self.loading_bar.pack_forget()
