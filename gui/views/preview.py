import threading
from pathlib import Path
import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
from gui.app import (COLOR_CARD, COLOR_TEXT, COLOR_TEXT_DIM, COLOR_ACCENT,
                     COLOR_ACCENT2, COLOR_BG, COLOR_SUCCESS, COLOR_WARNING,
                     COLOR_BORDER, COLOR_ERROR, FONT_FAMILY, FONT_SIZE_TITLE,
                     FONT_SIZE_HEADER, FONT_SIZE_BODY, FONT_SIZE_SMALL)
from utils.formatting import format_size, format_count


class PreviewView:
    def __init__(self, parent, app, main_window):
        self.parent = parent
        self.app = app
        self.main_window = main_window
        self._planning = False
        self._build()

    def _build(self):
        # Header
        header = ctk.CTkFrame(self.parent, fg_color='transparent', height=60)
        header.pack(fill='x', padx=20, pady=(20, 0))
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text='Preview da Organização',
            font=(FONT_FAMILY, FONT_SIZE_TITLE, 'bold'), text_color=COLOR_TEXT
        ).pack(side='left', pady=10)

        ctk.CTkButton(
            header, text='Gerar Preview',
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT2,
            corner_radius=8, width=140,
            command=self._generate_plan
        ).pack(side='right', pady=10)

        # Loading bar (hidden initially)
        self.loading_bar = ctk.CTkProgressBar(
            self.parent, mode='determinate', height=6,
            fg_color='#2a2a4a', progress_color=COLOR_ACCENT
        )

        # Tab view for Tree vs Grid
        self.tabview = ctk.CTkTabview(
            self.parent, fg_color=COLOR_CARD, corner_radius=12,
            segmented_button_fg_color=COLOR_CARD,
            segmented_button_selected_color=COLOR_ACCENT,
            segmented_button_unselected_color=COLOR_CARD
        )
        self.tabview.pack(fill='both', expand=True, padx=20, pady=12)

        self.tab_tree = self.tabview.add('Lista Estruturada')
        self.tab_grid = self.tabview.add('Galeria de Miniaturas')

        # Style treeview for dark theme
        style = ttk.Style()
        style.theme_use('clam')
        style.configure(
            'PhotoVault.Treeview',
            background='#1e2040', foreground=COLOR_TEXT,
            fieldbackground='#1e2040', borderwidth=0,
            font=(FONT_FAMILY, FONT_SIZE_BODY)
        )
        style.configure(
            'PhotoVault.Treeview.Heading',
            background=COLOR_CARD, foreground=COLOR_TEXT_DIM,
            font=(FONT_FAMILY, FONT_SIZE_SMALL, 'bold')
        )
        style.map('PhotoVault.Treeview', background=[('selected', COLOR_ACCENT)])

        tree_frame = ctk.CTkFrame(self.tab_tree, fg_color='transparent')
        tree_frame.pack(fill='both', expand=True, padx=10, pady=10)

        self.tree = ttk.Treeview(
            tree_frame, style='PhotoVault.Treeview',
            columns=('count', 'size', 'status'), show='tree headings'
        )
        self.tree.heading('#0', text='Destino')
        self.tree.heading('count', text='Arquivos')
        self.tree.heading('size', text='Tamanho')
        self.tree.heading('status', text='Status')
        self.tree.column('#0', width=400)
        self.tree.column('count', width=80, anchor='center')
        self.tree.column('size', width=100, anchor='e')
        self.tree.column('status', width=100, anchor='center')

        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        # --- GRID TAB ---
        self.grid_scroll = ctk.CTkScrollableFrame(self.tab_grid, fg_color='transparent')
        self.grid_scroll.pack(fill='both', expand=True, padx=5, pady=5)

        # Grid settings
        self._grid_cols = 5
        for i in range(self._grid_cols):
            self.grid_scroll.columnconfigure(i, weight=1)

        # Tag colors
        self.tree.tag_configure('new', foreground=COLOR_SUCCESS)
        self.tree.tag_configure('conflict', foreground=COLOR_WARNING)
        self.tree.tag_configure('exists', foreground=COLOR_TEXT_DIM)
        self.tree.tag_configure('folder', foreground=COLOR_ACCENT2)

        # Summary bar
        summary_frame = ctk.CTkFrame(self.parent, fg_color=COLOR_CARD, corner_radius=12)
        summary_frame.pack(fill='x', padx=20, pady=(0, 8))

        self.summary_label = ctk.CTkLabel(
            summary_frame, text='Gere um preview para ver a estrutura de destino.',
            font=(FONT_FAMILY, FONT_SIZE_BODY), text_color=COLOR_TEXT_DIM
        )
        self.summary_label.pack(side='left', padx=20, pady=12)

        # Legend
        legend = ctk.CTkFrame(summary_frame, fg_color='transparent')
        legend.pack(side='right', padx=20, pady=12)
        for label, color in [('Novo', COLOR_SUCCESS), ('Conflito', COLOR_WARNING), ('Já existe', COLOR_TEXT_DIM)]:
            ctk.CTkLabel(legend, text=f'● {label}',
                         font=(FONT_FAMILY, FONT_SIZE_SMALL),
                         text_color=color).pack(side='left', padx=6)

        # Navigation buttons
        nav = ctk.CTkFrame(self.parent, fg_color='transparent')
        nav.pack(fill='x', padx=20, pady=(0, 16))

        ctk.CTkButton(
            nav, text='◀ Voltar: Regras',
            font=(FONT_FAMILY, FONT_SIZE_BODY, 'bold'),
            fg_color='transparent', hover_color=COLOR_ACCENT,
            border_color=COLOR_ACCENT, border_width=1,
            corner_radius=8, width=180, height=44,
            command=lambda: self.main_window.navigate('rules')
        ).pack(side='left')

        ctk.CTkButton(
            nav, text='Próximo: Duplicatas ▶',
            font=(FONT_FAMILY, FONT_SIZE_BODY, 'bold'),
            fg_color=COLOR_ACCENT, hover_color=COLOR_ACCENT2,
            corner_radius=8, width=220, height=44,
            command=self._continue
        ).pack(side='right')

    def _generate_plan(self):
        if self._planning:
            return
        state = self.app.app_state
        sources = [s for s in state.get('sources', []) if s.get('type') != 'cloud']
        destination = state.get('destination')
        pattern = state.get('pattern', '{year}/{month:02d}')

        if not sources or not destination:
            self.summary_label.configure(text='Configure fontes e destino primeiro.')
            return

        self._planning = True
        self.summary_label.configure(text='Gerando plano...')
        self.loading_bar.set(0)
        self.loading_bar.pack(fill='x', padx=20, pady=(0, 4))
        self._clear_tree()

        def worker():
            try:
                from core.organizer import plan_organization
                from core.scanner import count_files

                pre_total = sum(
                    count_files(Path(s['path'])).get('total', 0) for s in sources
                )
                step = max(1, pre_total // 100)

                def cb(file, done):
                    if pre_total > 0 and done % step == 0:
                        val = min(done / pre_total, 1.0)
                        pct = int(val * 100)
                        self.parent.after(0, lambda v=val, p=pct, d=done, t=pre_total: (
                            self.loading_bar.set(v),
                            self.summary_label.configure(
                                text=f'Gerando plano... {d}/{t} arquivos ({p}%)')
                        ))

                if state.get('skip_existing', True):
                    self.parent.after(0, lambda: self.summary_label.configure(
                        text='Escaneando destino (primeira vez pode demorar)...'
                    ))

                plan = plan_organization(
                    sources=[Path(s['path']) for s in sources],
                    destination=destination,
                    pattern=pattern,
                    mode=state.get('mode', 'copy'),
                    include_no_date=state.get('include_no_date', True),
                    skip_existing=state.get('skip_existing', True),
                    callback=cb,
                )
                self.app.app_state['plan'] = plan
                self.parent.after(0, lambda: self._populate_tree(plan))
            except Exception as e:
                self.parent.after(0, lambda msg=str(e): self._on_plan_error(msg))

        threading.Thread(target=worker, daemon=True).start()

    def _clear_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for w in self.grid_scroll.winfo_children():
            w.destroy()

    def _on_plan_error(self, msg: str):
        self._planning = False
        self.loading_bar.pack_forget()
        self.summary_label.configure(
            text=f'Erro ao gerar plano: {msg}', text_color=COLOR_ERROR
        )

    def _populate_tree(self, plan):
        self._planning = False
        self.loading_bar.set(1.0)
        self.loading_bar.pack_forget()
        self._clear_tree()
        self._render_gen = getattr(self, '_render_gen', 0) + 1

        # Build folder tree
        folders: dict[str, dict] = {}
        ops_to_grid = []
        for op in plan.operations:
            ops_to_grid.append(op)
            try:
                parts = op.dst.relative_to(plan.destination).parts
            except ValueError:
                parts = (op.dst.name,)
            parent_key = ''
            for i, part in enumerate(parts[:-1]):
                key = '/'.join(parts[:i+1])
                if key not in folders:
                    tag = 'folder'
                    iid = self.tree.insert(
                        parent_key, 'end', iid=key,
                        text=f'📁 {part}', values=('', '', ''),
                        tags=(tag,), open=i < 2
                    )
                    folders[key] = {'count': 0, 'size': 0, 'iid': iid}
                parent_key = key
                folders[key]['count'] += 1
                try:
                    folders[key]['size'] += op.src.stat().st_size
                except OSError:
                    pass

            # File entry
            status = 'new'
            status_txt = 'Novo'
            try:
                size = op.src.stat().st_size
            except OSError:
                size = 0

            if op.dst.exists():
                status = 'conflict'
                status_txt = 'Conflito'

            self.tree.insert(
                parent_key, 'end',
                text=f'  {op.src.name}',
                values=(1, format_size(size), status_txt),
                tags=(status,)
            )

        # Update folder counts
        for key, data in folders.items():
            self.tree.item(key, values=(data['count'], format_size(data['size']), ''))

        # Summary
        total = len(plan.operations)
        conflicts = sum(1 for op in plan.operations if op.dst.exists())
        self.summary_label.configure(
            text=f'{format_count(total)} arquivos → {len(folders)} pastas  •  {conflicts} conflitos resolvidos'
        )

        # Grid rendering
        self._render_grid_batch(ops_to_grid, 0, self._render_gen)

    def _render_grid_batch(self, ops, start, gen, batch=20):
        if gen != self._render_gen:
            return

        end = min(start + batch, len(ops))
        from gui.widgets.thumbnail_viewer import ThumbnailViewer

        for i in range(start, end):
            op = ops[i]
            r, c = divmod(i, self._grid_cols)

            frame = ctk.CTkFrame(self.grid_scroll, fg_color='transparent')
            frame.grid(row=r, column=c, padx=5, pady=5, sticky='nsew')

            tv = ThumbnailViewer(frame, op.src, size=(140, 105))
            tv.pack()

            lbl = ctk.CTkLabel(
                frame, text=op.src.name,
                font=(FONT_FAMILY, 9), text_color=COLOR_TEXT_DIM,
                wraplength=130
            )
            lbl.pack()

        if end < len(ops) and end < 200: # Limit preview to first 200 for performance
            self.parent.after(50, lambda: self._render_grid_batch(ops, end, gen, batch))

    def _continue(self):
        if not self.app.app_state.get('plan'):
            self._generate_plan()
        else:
            self.main_window.navigate('duplicates')

    def refresh(self):
        if not self.app.app_state.get('plan'):
            self._clear_tree()
            self._planning = False
            self.loading_bar.pack_forget()
            self.summary_label.configure(
                text='Gere um preview para ver a estrutura de destino.',
                text_color=COLOR_TEXT_DIM
            )
