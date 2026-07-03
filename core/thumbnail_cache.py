import hashlib
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from PIL import Image, ImageOps

from utils.constants import CONFIG_DIR, VIDEO_EXTENSIONS

THUMB_DIR = CONFIG_DIR / "thumbs"
THUMB_SIZE = (360, 240)


def cache_key(path: Path) -> str:
    try:
        stat = path.stat()
        raw = f"{path.resolve()}|{stat.st_mtime_ns}|{stat.st_size}"
    except Exception:
        raw = str(path)
    return hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()


def thumbnail_path(path: Path) -> Path:
    return THUMB_DIR / f"{cache_key(path)}.jpg"


def get_cached_thumbnail(path: Path) -> Optional[Path]:
    thumb = thumbnail_path(path)
    if thumb.exists():
        return thumb
    return None


def ensure_thumbnail(path: Path, size: tuple[int, int] = THUMB_SIZE) -> Optional[Path]:
    cached = get_cached_thumbnail(path)
    if cached:
        return cached

    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    image = None
    try:
        if path.suffix.lower() in VIDEO_EXTENSIONS:
            image = _video_frame(path)
        else:
            with Image.open(path) as source:
                image = ImageOps.exif_transpose(source).convert("RGB")
        if image is None:
            return None
        preview = ImageOps.fit(image, size, Image.LANCZOS, centering=(0.5, 0.5))
        out = thumbnail_path(path)
        tmp = out.with_suffix(".tmp.jpg")
        preview.save(tmp, "JPEG", quality=82, optimize=True)
        tmp.replace(out)
        return out
    except Exception:
        return None
    finally:
        try:
            if image is not None:
                image.close()
        except Exception:
            pass


def _video_frame(path: Path):
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp_path = tmp.name
        result = subprocess.run(
            ["ffmpeg", "-i", str(path), "-ss", "00:00:01", "-vframes", "1", "-y", tmp_path],
            capture_output=True,
            timeout=10,
        )
        if result.returncode == 0 and os.path.exists(tmp_path):
            with Image.open(tmp_path) as source:
                return ImageOps.exif_transpose(source).convert("RGB")
    except Exception:
        return None
    finally:
        try:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except Exception:
            pass
    return None
