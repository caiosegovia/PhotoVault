import threading
from pathlib import Path

import customtkinter as ctk
from tkinter import ttk

from gui.app import (
    COLOR_ACCENT,
    COLOR_ACCENT2,
    COLOR_BORDER,
    COLOR_CARD,
    COLOR_ERROR,
    COLOR_SUCCESS,
    COLOR_TEXT,
    COLOR_TEXT_DIM,
    COLOR_WARNING,
    FONT_FAMILY,
    FONT_SIZE_BODY,
    FONT_SIZE_HEADER,
    FONT_SIZE_SMALL,
    FONT_SIZE_TITLE,
)
from utils.formatting import format_count, format_size


class PreviewView:
    def __init__(self, parent, app, main_window):
        self.parent = parent
        self.app = app
        self.main_window = main_window
        self._planning = False
        self._build()

    def _build(self):
        header = ctk.CTkFrame(self.parent, fg_color='transparent', height=60)
        header.pack(fill='x', padx=20, pady=(20, 0))
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text='Plano de Ingestao',
            font=(FONT_FAMILY, FONT_SIZE_TITLE, 'bold'),
            text_color=COLOR_TEXT,
        ).pack(side='left', pady=10)

        ctk.CTkButton(
            header,
            text='Regerar plano',
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT2,
            corner_radius=8,
            width=140,
            command=self._generate_plan,
        ).pack(side='right', pady=10)

        self.loading_bar = ctk.CTkProgressBar(
            self.parent,
            mode='determinate',
            height=6,
            fg_color=COLOR_BORDER,
            progress_color=COLOR_ACCENT,
        )

        tree_card = ctk.CTkFrame(self.parent, fg_color=COLOR_CARD, corner_radius=12)
        tree_card.pack(fill='both', expand=True, padx=20, pady=12)

        style = ttk.Style()
        style.theme_use('clam')
        style.configure(
            'PhotoVault.Treeview',
            background=COLOR_CARD,
            foreground=COLOR_TEXT,
            fieldbackground=COLOR_CARD,
            borderwidth=0,
            font=(FONT_FAMILY, FONT_SIZE_BODY),
        )
        style.configure(
            'PhotoVault.Treeview.Heading',
            background=COLOR_CARD,
            foreground=COLOR_TEXT_DIM,
            font=(FONT_FAMILY, FONT_SIZE_SMALL, 'bold'),
        )
        style.map('PhotoVault.Treeview', background=[('selected', COLOR_ACCENT)])

        tree_frame = ctk.CTkFrame(tree_card, fg_color='transparent')
        tree_frame.pack(fill='both', expand=True, padx=10, pady=10)

        self.tree = ttk.Treeview(
            tree_frame,
            style='PhotoVault.Treeview',
            columns=('count', 'size', 'status'),
            show='tree headings',
        )
        self.tree.heading('#0', text='Destino')
        self.tree.heading('count', text='Arquivos')
        self.tree.heading('size', text='Tamanho')
        self.tree.heading('status', text='Status')
        self.tree.column('#0', width=420)
        self.tree.column('count', width=80, anchor='center')
        self.tree.column('size', width=100, anchor='e')
        self.tree.column('status', width=130, anchor='center')

        vsb = ttk.Scrollbar(tree_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        self.tree.tag_configure('new', foreground=COLOR_SUCCESS)
        self.tree.tag_configure('conflict', foreground=COLOR_WARNING)
        self.tree.tag_configure('exists', foreground=COLOR_TEXT_DIM)
        self.tree.tag_configure('folder', foreground=COLOR_ACCENT2)

        summary_frame = ctk.CTkFrame(self.parent, fg_color=COLOR_CARD, corner_radius=12)
        summary_frame.pack(fill='x', padx=20, pady=(0, 8))

        self.summary_label = ctk.CTkLabel(
            summary_frame,
            text='Aprove a comparacao para ver o plano confiavel da galeria.',
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            text_color=COLOR_TEXT_DIM,
        )
        self.summary_label.pack(side='left', padx=20, pady=12)

        legend = ctk.CTkFrame(summary_frame, fg_color='transparent')
        legend.pack(side='right', padx=20, pady=12)
        for label, color in [('Novo', COLOR_SUCCESS), ('Duplicata', COLOR_TEXT_DIM), ('Conflito', COLOR_WARNING)]:
            ctk.CTkLabel(
                legend,
                text=f'- {label}',
                font=(FONT_FAMILY, FONT_SIZE_SMALL),
                text_color=color,
            ).pack(side='left', padx=6)

        nav = ctk.CTkFrame(self.parent, fg_color='transparent')
        nav.pack(fill='x', padx=20, pady=(0, 16))

        ctk.CTkButton(
            nav,
            text='Voltar',
            font=(FONT_FAMILY, FONT_SIZE_BODY),
            fg_color='transparent',
            hover_color=COLOR_ACCENT,
            border_color=COLOR_ACCENT,
            border_width=1,
            corner_radius=8,
            width=120,
            height=40,
            command=lambda: self.main_window.navigate('compare'),
        ).pack(side='left')

        ctk.CTkButton(
            nav,
            text='Continuar para executar',
            font=(FONT_FAMILY, FONT_SIZE_BODY, 'bold'),
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT2,
            corner_radius=8,
            width=220,
            height=40,
            command=self._continue,
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
        self.summary_label.configure(text='Criando plano confiavel...')
        self.loading_bar.set(0)
        self.loading_bar.pack(fill='x', padx=20, pady=(0, 4))
        self._clear_tree()

        def worker():
            try:
                from core.ingestion import build_ingest_plan
                from core.scanner import count_files

                pre_total = sum(count_files(Path(s['path'])).get('total', 0) for s in sources)
                step = max(1, pre_total // 100)

                def cb(_file, done):
                    if pre_total > 0 and done % step == 0:
                        val = min(done / pre_total, 1.0)
                        pct = int(val * 100)
                        self.parent.after(
                            0,
                            lambda v=val, p=pct, d=done, t=pre_total: (
                                self.loading_bar.set(v),
                                self.summary_label.configure(
                                    text=f'Catalogando arquivos... {d}/{t} ({p}%)'
                                ),
                            ),
                        )

                self.parent.after(
                    0,
                    lambda: self.summary_label.configure(
                        text='Calculando identidades SHA-256 e destino canonico...'
                    ),
                )
                plan = build_ingest_plan(
                    sources=[Path(s['path']) for s in sources],
                    vault_root=Path(destination),
                    pattern=pattern,
                    mode=state.get('mode', 'copy'),
                    callback=cb,
                )
                self.app.app_state['plan'] = plan
                self.app.app_state['plan_kind'] = 'ingest'
                self.app.app_state['ingest_plan_id'] = plan.plan_id
                self.parent.after(0, lambda: self._populate_tree(plan))
            except Exception as exc:
                self.parent.after(0, lambda msg=str(exc): self._on_plan_error(msg))

        threading.Thread(target=worker, daemon=True).start()

    def _clear_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

    def _on_plan_error(self, msg: str):
        self._planning = False
        self.loading_bar.pack_forget()
        self.summary_label.configure(text=f'Erro ao gerar plano: {msg}', text_color=COLOR_ERROR)

    def _populate_tree(self, plan):
        self._planning = False
        self.loading_bar.set(1.0)
        self.loading_bar.pack_forget()
        self._clear_tree()

        folders: dict[str, dict] = {}
        destination = plan.vault.root_path if hasattr(plan, 'vault') else plan.destination

        for op in plan.operations:
            src = Path(op['src_path']) if isinstance(op, dict) else op.src
            dst = Path(op['dst_path']) if isinstance(op, dict) else op.dst
            action = op.get('action', 'copy') if isinstance(op, dict) else op.action
            reason = op.get('reason', '') if isinstance(op, dict) else (op.error or '')
            size = op.get('size', 0) if isinstance(op, dict) else 0
            if not size:
                try:
                    size = src.stat().st_size
                except OSError:
                    size = 0

            try:
                parts = dst.relative_to(destination).parts
            except ValueError:
                parts = (dst.name,)

            parent_key = ''
            for i, part in enumerate(parts[:-1]):
                key = '/'.join(parts[:i + 1])
                if key not in folders:
                    iid = self.tree.insert(
                        parent_key,
                        'end',
                        iid=key,
                        text=f'[Pasta] {part}',
                        values=('', '', ''),
                        tags=('folder',),
                        open=i < 2,
                    )
                    folders[key] = {'count': 0, 'size': 0, 'iid': iid}
                parent_key = key
                folders[key]['count'] += 1
                folders[key]['size'] += size

            status = 'new'
            status_txt = 'Novo'
            if action == 'skip':
                status = 'exists'
                status_txt = 'Duplicata'
            elif dst.exists():
                status = 'conflict'
                status_txt = 'Conflito'
            if reason == 'already_in_vault':
                status_txt = 'No vault'

            self.tree.insert(
                parent_key,
                'end',
                text=f'  {src.name}',
                values=(1, format_size(size), status_txt),
                tags=(status,),
            )

        for key, data in folders.items():
            self.tree.item(key, values=(data['count'], format_size(data['size']), ''))

        total = len(plan.operations)
        skipped = sum(
            1 for op in plan.operations
            if (op.get('action') if isinstance(op, dict) else op.action) == 'skip'
        )
        new_items = total - skipped
        self.summary_label.configure(
            text=(
                f'{format_count(total)} itens analisados | '
                f'{format_count(new_items)} novos | '
                f'{format_count(skipped)} duplicatas/ja existentes'
            ),
            text_color=COLOR_TEXT_DIM,
        )

    def _continue(self):
        if not self.app.app_state.get('plan'):
            self._generate_plan()
        else:
            self.main_window.navigate('progress')

    def refresh(self):
        plan = self.app.app_state.get('plan')
        if not plan:
            self._clear_tree()
            self._planning = False
            self.loading_bar.pack_forget()
            self.summary_label.configure(
                text='Aprove a comparacao para ver o plano confiavel da galeria.',
                text_color=COLOR_TEXT_DIM,
            )
        else:
            self._populate_tree(plan)
