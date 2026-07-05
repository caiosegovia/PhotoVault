import logging
import shutil
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
