import logging
import json
import os
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Optional

from utils.constants import CONFIG_DIR

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
def perl_path() -> Optional[str]:
    return shutil.which("perl") or shutil.which("perl.exe")


def _settings_exiftool_path() -> Optional[Path]:
    settings_path = CONFIG_DIR / "settings.json"
    try:
        data = json.loads(settings_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    value = data.get("exiftoolPath")
    return Path(value) if value else None


def _exiftool_children(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return [
        path / "exiftool.exe",
        path / "exiftool(-k).exe",
        path / "exiftool",
    ]


def _exiftool_candidates() -> list[Path]:
    candidates: list[Path] = []
    explicit = Path(raw) if (raw := os.environ.get("PHOTOVAULT_EXIFTOOL")) else _settings_exiftool_path()
    if explicit:
        return _exiftool_children(explicit)

    for name in ("exiftool.exe", "exiftool"):
        found = shutil.which(name)
        if found:
            candidates.extend(_exiftool_children(Path(found)))

    downloads = Path.home() / "Downloads"
    for pattern in ("exiftool-*", "Image-ExifTool-*"):
        for folder in downloads.glob(pattern):
            candidates.extend(_exiftool_children(folder))
            for nested in folder.glob(pattern):
                candidates.extend(_exiftool_children(nested))
    return candidates


def _command_for_candidate(path: Path) -> Optional[list[str]]:
    if not path.exists():
        return None
    if path.suffix.lower() == ".exe":
        if path.name.lower() == "exiftool(-k).exe":
            path = _normalized_exiftool_exe(path)
        return [str(path)]
    if path.name.lower() == "exiftool":
        perl = perl_path()
        if perl:
            return [perl, str(path)]
    return None


def _normalized_exiftool_exe(path: Path) -> Path:
    target = CONFIG_DIR / "tools" / "exiftool.exe"
    source_files = path.parent / "exiftool_files"
    target_files = target.parent / "exiftool_files"
    try:
        if not target.exists() or target.stat().st_size != path.stat().st_size:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        if source_files.exists() and not target_files.exists():
            shutil.copytree(source_files, target_files)
    except OSError as exc:
        log.debug("exiftool copy failed source=%s target=%s error=%s", path, target, exc)
        return path
    return target


@lru_cache(maxsize=1)
def exiftool_command() -> Optional[list[str]]:
    """Return the command prefix needed to run ExifTool."""
    seen: set[str] = set()
    for candidate in _exiftool_candidates():
        key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        command = _command_for_candidate(candidate)
        if command:
            return command
    return None


@lru_cache(maxsize=1)
def exiftool_path() -> Optional[str]:
    """Return the selected ExifTool file path when it is runnable."""
    command = exiftool_command()
    if not command:
        return None
    return command[-1]


def exiftool_status() -> dict:
    discovered = next((path for path in _exiftool_candidates() if path.exists()), None)
    command = exiftool_command()
    if command:
        return {
            "available": True,
            "path": command[-1],
            "command": command,
            "reason": "ready",
        }
    if discovered and discovered.name.lower() == "exiftool" and not perl_path():
        return {
            "available": False,
            "path": str(discovered),
            "command": [],
            "reason": "perl_missing",
        }
    return {
        "available": False,
        "path": str(discovered) if discovered else "",
        "command": [],
        "reason": "not_found",
    }


@lru_cache(maxsize=1)
def exiftool_version() -> Optional[str]:
    """Return the ExifTool version without making it a hard dependency."""
    tool = exiftool_path()
    command = exiftool_command()
    if not tool or not command:
        return None
    try:
        result = subprocess.run(
            [*command, "-ver"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return (result.stdout.strip().splitlines() or [None])[0]
    except Exception as exc:
        log.debug("exiftool version check failed: %s", exc)
    return None


def has_exiftool() -> bool:
    return exiftool_command() is not None
