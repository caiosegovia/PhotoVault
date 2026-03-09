import customtkinter as ctk
from utils.formatting import format_size, format_count

COLOR_CARD = '#0f3460'
COLOR_TEXT = '#e0e0e0'
COLOR_TEXT_DIM = '#888888'
COLOR_ERROR = '#e74c3c'
FONT_FAMILY = 'Segoe UI'


class SourceCard(ctk.CTkFrame):
    def __init__(self, parent, source_info: dict, on_remove=None, **kw):
        super().__init__(parent, fg_color=COLOR_CARD, corner_radius=10, **kw)
        self.source_info = source_info
        self.on_remove = on_remove
        self._build()

    def _build(self):
        inner = ctk.CTkFrame(self, fg_color='transparent')
        inner.pack(fill='x', padx=16, pady=12)

        src_type = self.source_info.get('type', 'local')
        icon = {'local': '📁', 'drive': '💾', 'cloud': '☁'}.get(src_type, '📁')

        ctk.CTkLabel(inner, text=icon, font=(FONT_FAMILY, 22)).pack(side='left', padx=(0, 12))

        info_col = ctk.CTkFrame(inner, fg_color='transparent')
        info_col.pack(side='left', fill='x', expand=True)

        path_txt = str(self.source_info.get('path', ''))
        ctk.CTkLabel(
            info_col, text=path_txt,
            font=(FONT_FAMILY, 12), text_color=COLOR_TEXT, anchor='w'
        ).pack(anchor='w')

        details = []
        total = self.source_info.get('total', 0)
        if total:
            details.append(f"{format_count(total)} arquivos")
        size = self.source_info.get('size_bytes', 0)
        if size:
            details.append(format_size(size))

        ctk.CTkLabel(
            info_col, text='  •  '.join(details) or '—',
            font=(FONT_FAMILY, 10), text_color=COLOR_TEXT_DIM, anchor='w'
        ).pack(anchor='w')

        if self.on_remove:
            ctk.CTkButton(
                inner, text='✕', width=30, height=30,
                fg_color='transparent', hover_color=COLOR_ERROR,
                font=(FONT_FAMILY, 12),
                command=lambda: self.on_remove(self.source_info)
            ).pack(side='right')
