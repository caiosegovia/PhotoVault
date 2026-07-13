import hashlib
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont, ImageOps

from core.runtime_tools import ffmpeg_path
from utils.constants import CONFIG_DIR, VIDEO_EXTENSIONS

THUMB_DIR = CONFIG_DIR / "thumbs"
THUMB_SIZE = (360, 240)
THUMB_VERSION = "v2-fit-3x2"
log = logging.getLogger(__name__)


def cache_key(path: Path) -> str:
    try:
        stat = path.stat()
        raw = f"{THUMB_VERSION}|{path.resolve()}|{stat.st_mtime_ns}|{stat.st_size}"
    except Exception:
        raw = f"{THUMB_VERSION}|{path}"
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
            image = _placeholder(path, size)
        preview = ImageOps.fit(image, size, Image.LANCZOS, centering=(0.5, 0.5))
        out = thumbnail_path(path)
        tmp = out.with_suffix(".tmp.jpg")
        preview.save(tmp, "JPEG", quality=82, optimize=True)
        tmp.replace(out)
        return out
    except Exception as exc:
        log.debug("thumbnail generation failed path=%s error=%s", path, exc)
        try:
            out = thumbnail_path(path)
            _placeholder(path, size).save(out, "JPEG", quality=82, optimize=True)
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
    ffmpeg = ffmpeg_path()
    if not ffmpeg:
        log.info("ffmpeg unavailable for video thumbnail path=%s", path)
        return None
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp_path = tmp.name
        result = subprocess.run(
            [ffmpeg, "-hide_banner", "-loglevel", "error", "-ss", "00:00:01", "-i", str(path), "-frames:v", "1", "-q:v", "4", "-y", tmp_path],
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


def _placeholder(path: Path, size: tuple[int, int]):
    ext = (path.suffix or "media").replace(".", "").upper()
    kind = "VIDEO" if path.suffix.lower() in VIDEO_EXTENSIONS else "PREVIEW"
    image = Image.new("RGB", size, "#11161a")
    draw = ImageDraw.Draw(image)
    w, h = size
    draw.rectangle((0, 0, w - 1, h - 1), outline="#323a42")
    draw.rectangle((14, 14, w - 14, h - 14), outline="#252c32")
    font = ImageFont.load_default()
    title = f"{kind} {ext}"
    name = path.name[:42]
    draw.text((22, h // 2 - 18), title, fill="#32d3a6", font=font)
    draw.text((22, h // 2 + 4), name, fill="#a5afb8", font=font)
    return image
