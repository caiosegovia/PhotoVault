import logging
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def ffmpeg_path() -> Optional[str]:
    """Return a usable ffmpeg executable from PATH or imageio-ffmpeg."""
    system = shutil.which("ffmpeg")
    if system:
        return system
    try:
        import imageio_ffmpeg

        candidate = Path(imageio_ffmpeg.get_ffmpeg_exe())
        if candidate.exists():
            return str(candidate)
    except Exception as exc:
        log.debug("imageio-ffmpeg unavailable: %s", exc)
    return None


@lru_cache(maxsize=1)
def ffprobe_path() -> Optional[str]:
    """Return ffprobe when the system provides it."""
    return shutil.which("ffprobe")


def has_ffmpeg() -> bool:
    return ffmpeg_path() is not None


@lru_cache(maxsize=1)
def exiftool_path() -> Optional[str]:
    """Return ExifTool only when the operating system provides it on PATH."""
    return shutil.which("exiftool") or shutil.which("exiftool.exe")


@lru_cache(maxsize=1)
def exiftool_version() -> Optional[str]:
    """Return the ExifTool version without making it a hard dependency."""
    tool = exiftool_path()
    if not tool:
        return None
    try:
        result = subprocess.run(
            [tool, "-ver"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip() or None
    except Exception as exc:
        log.debug("exiftool version check failed: %s", exc)
    return None


def has_exiftool() -> bool:
    return exiftool_path() is not None
