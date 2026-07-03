import customtkinter as ctk

from gui.theme import ERROR, FONT_FAMILY, SURFACE, SURFACE_ALT, TEXT, TEXT_MUTED
from utils.formatting import format_count, format_size


class SourceCard(ctk.CTkFrame):
    def __init__(self, parent, source_info: dict, on_remove=None, **kw):
        super().__init__(
            parent,
            fg_color=SURFACE,
            corner_radius=8,
            border_width=1,
            border_color=SURFACE_ALT,
            **kw,
        )
        self.source_info = source_info
        self.on_remove = on_remove
        self._build()

    def _build(self):
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=12)

        src_type = self.source_info.get("type", "local")
        icon = {"local": "DIR", "drive": "HD", "cloud": "CLD"}.get(src_type, "SRC")

        ctk.CTkLabel(inner, text=icon, font=(FONT_FAMILY, 12, "bold"), text_color=TEXT_MUTED).pack(
            side="left", padx=(0, 12)
        )

        info_col = ctk.CTkFrame(inner, fg_color="transparent")
        info_col.pack(side="left", fill="x", expand=True)

        path_txt = str(self.source_info.get("path", ""))
        ctk.CTkLabel(
            info_col,
            text=path_txt,
            font=(FONT_FAMILY, 12),
            text_color=TEXT,
            anchor="w",
        ).pack(anchor="w")

        details = []
        total = self.source_info.get("total", 0)
        if total:
            details.append(f"{format_count(total)} arquivos")
        size = self.source_info.get("size_bytes", 0)
        if size:
            details.append(format_size(size))

        ctk.CTkLabel(
            info_col,
            text="  |  ".join(details) or "-",
            font=(FONT_FAMILY, 10),
            text_color=TEXT_MUTED,
            anchor="w",
        ).pack(anchor="w")

        if self.on_remove:
            ctk.CTkButton(
                inner,
                text="X",
                width=30,
                height=30,
                fg_color="transparent",
                hover_color=ERROR,
                font=(FONT_FAMILY, 12, "bold"),
                command=lambda: self.on_remove(self.source_info),
            ).pack(side="right")
