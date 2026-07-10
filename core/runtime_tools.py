import logging
import json
import os
import platform
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from typing import Optional

from utils.constants import CONFIG_DIR, DB_PATH
from utils.logging import get_log_path

log = logging.getLogger(__name__)


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _static_media_tool(name: str) -> Optional[str]:
    package_dir = _repo_root() / "frontend" / "node_modules" / "ffmpeg-ffprobe-static"
    candidates = [
        package_dir / f"{name}.exe",
        package_dir / name,
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


@lru_cache(maxsize=1)
def ffmpeg_path() -> Optional[str]:
    """Return a usable ffmpeg executable from static package, PATH or imageio-ffmpeg."""
    explicit = os.environ.get("PHOTOVAULT_FFMPEG")
    if explicit and Path(explicit).exists():
        return explicit
    static = _static_media_tool("ffmpeg")
    if static:
        return static
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
    """Return ffprobe from static package or PATH."""
    explicit = os.environ.get("PHOTOVAULT_FFPROBE")
    if explicit and Path(explicit).exists():
        return explicit
    return _static_media_tool("ffprobe") or shutil.which("ffprobe")


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


def _first_tool_path(*names: str) -> Optional[str]:
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    return None


def _tool_entry(label: str, path: Optional[str], required: bool = True,
                version: Optional[str] = None, detail: str = "") -> dict:
    ok = bool(path)
    return {
        "label": label,
        "available": ok,
        "required": required,
        "path": path or "",
        "version": version or "",
        "status": "ok" if ok else ("error" if required else "warning"),
        "detail": detail,
    }


def _path_entry(label: str, path: Path, required: bool = True) -> dict:
    exists = path.exists()
    parent = path if path.is_dir() else path.parent
    writable = os.access(str(parent), os.W_OK) if parent.exists() else os.access(str(parent.parent), os.W_OK)
    ok = bool((exists or not required) and writable)
    return {
        "label": label,
        "available": ok,
        "required": required,
        "path": str(path),
        "version": "",
        "status": "ok" if ok else ("error" if required else "warning"),
        "detail": "gravavel" if writable else "sem permissao de escrita",
    }


def environment_diagnostics() -> dict:
    """Return local runtime readiness for the desktop app and dev workflow."""
    ffmpeg = ffmpeg_path()
    ffprobe = ffprobe_path()
    exif_status = exiftool_status()
    tools = [
        _tool_entry("Python", sys.executable, version=platform.python_version()),
        _tool_entry("Node.js", _first_tool_path("node.exe", "node")),
        _tool_entry("npm", _first_tool_path("npm.cmd", "npm.exe", "npm")),
        _tool_entry("Cargo", _first_tool_path("cargo.exe", "cargo")),
        _tool_entry("ffmpeg", ffmpeg, required=False, detail="necessario para previews de video"),
        _tool_entry("ffprobe", ffprobe, required=False, detail="melhora metadados de video"),
        _tool_entry(
            "ExifTool",
            exif_status.get("path") if exif_status.get("available") else None,
            required=False,
            version=exiftool_version(),
            detail=exif_status.get("reason") or "",
        ),
    ]
    paths = [
        _path_entry("Config local", CONFIG_DIR, required=False),
        _path_entry("Banco SQLite", DB_PATH, required=False),
        _path_entry("Log", get_log_path(), required=False),
    ]
    checks = tools + paths
    required_missing = [item for item in checks if item.get("required") and item.get("status") != "ok"]
    optional_missing = [item for item in checks if not item.get("required") and item.get("status") != "ok"]
    status = "ok" if not required_missing else "error"
    return {
        "status": status,
        "summary": (
            "Ambiente pronto"
            if status == "ok"
            else f"{len(required_missing)} requisito(s) obrigatorio(s) ausente(s)"
        ),
        "requiredMissing": len(required_missing),
        "optionalMissing": len(optional_missing),
        "tools": tools,
        "paths": paths,
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
    }
