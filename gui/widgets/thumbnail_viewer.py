from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import customtkinter as ctk
from PIL import Image

from core.thumbnail_cache import ensure_thumbnail, get_cached_thumbnail
from gui.theme import ACCENT, SURFACE_MUTED, TEXT_MUTED

_THUMBNAIL_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="thumb")
_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".m4v", ".3gp", ".wmv", ".mts", ".m2ts"}


class ThumbnailViewer(ctk.CTkFrame):
    def __init__(self, parent, path: Path, size: tuple = (160, 120), **kw):
        super().__init__(parent, fg_color=SURFACE_MUTED, corner_radius=8, **kw)
        self.path = path
        self.size = size
        self._photo = None
        self._is_video = path.suffix.lower() in _VIDEO_EXTENSIONS

        self.configure(width=size[0], height=size[1])
        self.pack_propagate(False)

        self.label = ctk.CTkLabel(self, text="...", font=("Segoe UI", 20), text_color=TEXT_MUTED)
        self.label.pack(expand=True)

        _THUMBNAIL_POOL.submit(self._load)

    def _load(self):
        try:
            thumb_path = get_cached_thumbnail(self.path) or ensure_thumbnail(self.path)
            if not thumb_path:
                self.after(0, self._show_placeholder)
                return
            with Image.open(thumb_path) as source:
                preview = source.copy()
            self.after(0, lambda image=preview: self._show(image))
        except Exception:
            self.after(0, self._show_placeholder)

    def _show(self, image):
        try:
            self._photo = ctk.CTkImage(light_image=image, dark_image=image, size=self.size)
            self.label.configure(image=self._photo, text="")
            if self._is_video:
                ctk.CTkLabel(
                    self,
                    text="VIDEO",
                    font=("Segoe UI", 9, "bold"),
                    text_color="white",
                    fg_color=ACCENT,
                    corner_radius=5,
                    height=18,
                ).place(relx=0.04, rely=0.07, anchor="nw")
        except Exception:
            self._show_placeholder()

    def _show_placeholder(self):
        label = "VIDEO" if self._is_video else "SEM PREVIEW"
        try:
            self.label.configure(text=label, image=None, font=("Segoe UI", 12, "bold"), text_color=TEXT_MUTED)
        except Exception:
            pass
