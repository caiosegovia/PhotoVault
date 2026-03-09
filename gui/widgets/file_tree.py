import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
from utils.formatting import format_size, format_count


class FileTree(ctk.CTkFrame):
    def __init__(self, parent, **kw):
        super().__init__(parent, **kw)
        self._build()

    def _build(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure(
            'FileTree.Treeview',
            background='#1e2040', foreground='#e0e0e0',
            fieldbackground='#1e2040', borderwidth=0,
            font=('Segoe UI', 11)
        )
        style.configure(
            'FileTree.Treeview.Heading',
            background='#0f3460', foreground='#888888',
            font=('Segoe UI', 10, 'bold')
        )
        style.map('FileTree.Treeview', background=[('selected', '#0d7377')])

        frame = ctk.CTkFrame(self, fg_color='transparent')
        frame.pack(fill='both', expand=True)

        self.tree = ttk.Treeview(
            frame, style='FileTree.Treeview',
            columns=('count', 'size', 'status'), show='tree headings'
        )
        self.tree.heading('#0', text='Caminho')
        self.tree.heading('count', text='Arquivos')
        self.tree.heading('size', text='Tamanho')
        self.tree.heading('status', text='Status')
        self.tree.column('#0', width=420)
        self.tree.column('count', width=80, anchor='center')
        self.tree.column('size', width=100, anchor='e')
        self.tree.column('status', width=100, anchor='center')

        vsb = ttk.Scrollbar(frame, orient='vertical', command=self.tree.yview)
        hsb = ttk.Scrollbar(frame, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        self.tree.tag_configure('new', foreground='#2ecc71')
        self.tree.tag_configure('conflict', foreground='#f39c12')
        self.tree.tag_configure('exists', foreground='#888888')
        self.tree.tag_configure('folder', foreground='#14a085')

    def load_plan(self, plan):
        self.clear()
        folders: dict[str, dict] = {}

        for op in plan.operations:
            try:
                parts = op.dst.relative_to(plan.destination).parts
            except ValueError:
                continue

            parent_key = ''
            for i, part in enumerate(parts[:-1]):
                key = '/'.join(parts[:i+1])
                if key not in folders:
                    iid = self.tree.insert(
                        parent_key, 'end', iid=key,
                        text=f'  📁 {part}', values=('', '', ''),
                        tags=('folder',), open=i < 2
                    )
                    folders[key] = {'count': 0, 'size': 0}
                parent_key = key
                folders[key]['count'] += 1
                try:
                    folders[key]['size'] += op.src.stat().st_size
                except OSError:
                    pass

            tag = 'conflict' if op.dst.exists() else 'new'
            status = 'Conflito' if op.dst.exists() else 'Novo'
            try:
                size = op.src.stat().st_size
            except OSError:
                size = 0

            self.tree.insert(
                parent_key, 'end',
                text=f'    {op.src.name}',
                values=(1, format_size(size), status),
                tags=(tag,)
            )

        for key, data in folders.items():
            self.tree.item(key, values=(data['count'], format_size(data['size']), ''))

    def clear(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

    def expand_all(self):
        def _expand(node):
            self.tree.item(node, open=True)
            for child in self.tree.get_children(node):
                _expand(child)
        for node in self.tree.get_children():
            _expand(node)

    def collapse_all(self):
        def _collapse(node):
            self.tree.item(node, open=False)
            for child in self.tree.get_children(node):
                _collapse(child)
        for node in self.tree.get_children():
            _collapse(node)
