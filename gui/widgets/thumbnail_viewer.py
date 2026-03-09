import threading
import customtkinter as ctk
from pathlib import Path
from PIL import Image


class ThumbnailViewer(ctk.CTkFrame):
    def __init__(self, parent, path: Path, size: tuple = (160, 120), **kw):
        super().__init__(parent, fg_color='#111122', corner_radius=8, **kw)
        self.path = path
        self.size = size
        self._photo = None

        self.configure(width=size[0], height=size[1])
        self.pack_propagate(False)

        self.label = ctk.CTkLabel(self, text='⟳', font=('Segoe UI', 20), text_color='#888')
        self.label.pack(expand=True)

        threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        try:
            ext = self.path.suffix.lower()
            if ext in {'.mp4', '.mov', '.avi', '.mkv', '.m4v', '.3gp', '.wmv', '.mts', '.m2ts'}:
                img = self._video_thumbnail()
            else:
                img = Image.open(self.path)

            if img:
                img.thumbnail(self.size, Image.LANCZOS)
                # Pad to exact size
                bg = Image.new('RGB', self.size, (17, 17, 34))
                offset = ((self.size[0] - img.width) // 2, (self.size[1] - img.height) // 2)
                bg.paste(img, offset)
                self._photo = ctk.CTkImage(light_image=bg, dark_image=bg, size=self.size)
                self.after(0, self._show)
        except Exception:
            self.after(0, lambda: self.label.configure(text='🖼', font=('Segoe UI', 24)))

    def _video_thumbnail(self):
        """Try to extract a video frame thumbnail."""
        try:
            import subprocess, tempfile, os
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                tmp_path = tmp.name

            result = subprocess.run(
                ['ffmpeg', '-i', str(self.path), '-ss', '00:00:01',
                 '-vframes', '1', '-y', tmp_path],
                capture_output=True, timeout=10
            )
            if result.returncode == 0 and os.path.exists(tmp_path):
                img = Image.open(tmp_path)
                os.unlink(tmp_path)
                return img
        except Exception:
            pass
        return None

    def _show(self):
        if self._photo:
            try:
                self.label.configure(image=self._photo, text='')
            except Exception:
                pass
