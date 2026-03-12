import logging
import customtkinter as ctk
from pathlib import Path
from PIL import Image
from functools import lru_cache
import threading

# Global cache for ctk.CTkImage objects (stores up to 500 images to prevent memory explosion)
# Note: lru_cache on a method would keep 'self' alive. We use a manual cache or global.
THUMBNAIL_CACHE = {}
CACHE_LOCK = threading.Lock()
MAX_CACHE_SIZE = 500

class ThumbnailViewer(ctk.CTkFrame):
    def __init__(self, parent, path: Path, size: tuple = (160, 120), **kw):
        super().__init__(parent, fg_color='#111122', corner_radius=8, **kw)
        self.path = path
        self.size = size
        self.app = parent.winfo_toplevel() # Should be PhotoVaultApp
        self._photo = None
        self._cancelled = False

        self.configure(width=size[0], height=size[1])
        self.pack_propagate(False)

        self.label = ctk.CTkLabel(self, text='⟳', font=('Segoe UI', 16), text_color='#444')
        self.label.pack(expand=True)

        self._start_load()

    def _start_load(self):
        # Check cache first
        cache_key = (str(self.path), self.size)
        with CACHE_LOCK:
            if cache_key in THUMBNAIL_CACHE:
                self._photo = THUMBNAIL_CACHE[cache_key]
                self._show()
                return

        # Use global executor from app
        if hasattr(self.app, 'executor'):
            self.app.executor.submit(self._load)
        else:
            # Fallback if app not initialized yet
            threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        if self._cancelled: return
        try:
            ext = self.path.suffix.lower()
            if ext in {'.mp4', '.mov', '.avi', '.mkv', '.m4v', '.3gp', '.wmv', '.mts', '.m2ts'}:
                img = self._video_thumbnail()
            else:
                img = Image.open(self.path)

            if img and not self._cancelled:
                img.thumbnail(self.size, Image.LANCZOS)
                # Pad to exact size for consistent grid alignment
                bg = Image.new('RGBA', self.size, (0, 0, 0, 0)) # Transparent padding
                offset = ((self.size[0] - img.width) // 2, (self.size[1] - img.height) // 2)
                bg.paste(img, offset)
                
                # Create CTkImage (must be on main thread technically, but ctk handles it)
                self._photo = ctk.CTkImage(light_image=bg, dark_image=bg, size=self.size)
                
                # Add to cache
                cache_key = (str(self.path), self.size)
                with CACHE_LOCK:
                    if len(THUMBNAIL_CACHE) >= MAX_CACHE_SIZE:
                        # Simple FIFO eviction
                        first_key = next(iter(THUMBNAIL_CACHE))
                        del THUMBNAIL_CACHE[first_key]
                    THUMBNAIL_CACHE[cache_key] = self._photo

                self.after(0, self._show)
        except Exception as e:
            if not self._cancelled:
                logging.debug(f"Failed to load thumbnail for {self.path}: {e}")
                self.after(0, lambda: self.label.configure(text='✕', font=('Segoe UI', 18)))

    def _video_thumbnail(self):
        """Extract a video frame thumbnail using ffmpeg with optimization."""
        try:
            import subprocess, tempfile, os
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                tmp_path = tmp.name

            # Use faster ffmpeg flags
            result = subprocess.run(
                ['ffmpeg', '-ss', '00:00:01', '-i', str(self.path),
                 '-vframes', '1', '-q:v', '2', '-y', tmp_path],
                capture_output=True, timeout=5,
                creationflags=0x08000000 # CREATE_NO_WINDOW on Windows
            )
            if result.returncode == 0 and os.path.exists(tmp_path):
                img = Image.open(tmp_path)
                img.load() # Force load into memory
                os.unlink(tmp_path)
                return img
        except Exception:
            pass
        return None

    def _show(self):
        if self._photo and not self._cancelled:
            try:
                self.label.configure(image=self._photo, text='')
            except Exception:
                pass

    def destroy(self):
        self._cancelled = True
        super().destroy()
