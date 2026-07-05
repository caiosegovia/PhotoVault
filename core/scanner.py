import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Callable, Optional, Set

from utils.constants import ALL_MEDIA_EXTENSIONS, PHOTO_EXTENSIONS, VIDEO_EXTENSIONS


@dataclass
class ScanReport:
    errors: list[dict] = field(default_factory=list)

    def add_error(self, path: Path, error: OSError) -> None:
        self.errors.append({'path': str(path), 'error': str(error)})


def scan_directory(
    path: Path,
    extensions: Optional[Set[str]] = None,
    recursive: bool = True,
    callback: Optional[Callable[[Path, int], None]] = None,
    report: Optional[ScanReport] = None,
) -> Iterator[Path]:
    """
    Discover media files in directory.
    callback(current_file, total_found) is called for each file found.
    """
    if extensions is None:
        extensions = ALL_MEDIA_EXTENSIONS

    exts_lower = {e.lower() for e in extensions}
    total_found = 0

    def onerror(error: OSError) -> None:
        if report:
            report.add_error(Path(getattr(error, 'filename', None) or path), error)

    try:
        if recursive:
            walker = os.walk(path, onerror=onerror)
        else:
            try:
                names = os.listdir(path)
            except OSError as exc:
                onerror(exc)
                return
            walker = [(str(path), [], names)]

        for root, _dirs, files in walker:
            for name in files:
                item = Path(root) / name
                if item.suffix.lower() not in exts_lower:
                    continue
                try:
                    if not item.is_file():
                        continue
                except OSError as exc:
                    onerror(exc)
                    continue
                total_found += 1
                if callback:
                    callback(item, total_found)
                yield item
    except OSError as exc:
        onerror(exc)


def count_files(path: Path, extensions: Optional[Set[str]] = None,
                report: Optional[ScanReport] = None) -> dict:
    """Count files by type in directory."""
    if extensions is None:
        extensions = ALL_MEDIA_EXTENSIONS

    total = 0
    photos = 0
    videos = 0
    others = 0
    size_bytes = 0

    def onerror(error: OSError) -> None:
        if report:
            report.add_error(Path(getattr(error, 'filename', None) or path), error)

    try:
        for root, _dirs, files in os.walk(path, onerror=onerror):
            for name in files:
                item = Path(root) / name
                ext = item.suffix.lower()
                if ext not in extensions:
                    continue
                try:
                    if not item.is_file():
                        continue
                    size_bytes += item.stat().st_size
                except OSError as exc:
                    onerror(exc)
                    continue
                total += 1
                if ext in PHOTO_EXTENSIONS:
                    photos += 1
                elif ext in VIDEO_EXTENSIONS:
                    videos += 1
                else:
                    others += 1
    except OSError as exc:
        onerror(exc)

    return {
        'total': total,
        'photos': photos,
        'videos': videos,
        'others': others,
        'size_bytes': size_bytes,
        'errors': len(report.errors) if report else 0,
    }


def get_drive_info(path: Path) -> dict:
    """Get disk usage info for the drive containing path."""
    import shutil
    try:
        usage = shutil.disk_usage(str(path))
        return {
            'total_space': usage.total,
            'used_space': usage.used,
            'free_space': usage.free,
        }
    except Exception:
        return {
            'total_space': 0,
            'used_space': 0,
            'free_space': 0,
        }


def detect_drives() -> list[dict]:
    """Detect mounted drives/volumes."""
    import platform
    drives = []

    if platform.system() == 'Windows':
        import string
        for letter in string.ascii_uppercase:
            p = Path(f"{letter}:\\")
            if p.exists():
                info = get_drive_info(p)
                drives.append({'path': p, 'label': f"{letter}:", **info})
    else:
        # Linux/macOS: check /media, /mnt, /Volumes
        for base in [Path('/media'), Path('/mnt'), Path('/Volumes')]:
            if base.exists():
                for mount in base.iterdir():
                    if mount.is_dir():
                        info = get_drive_info(mount)
                        if info['total_space'] > 0:
                            drives.append({'path': mount, 'label': mount.name, **info})
        # Always include home
        home = Path.home()
        info = get_drive_info(home)
        drives.insert(0, {'path': home, 'label': 'Home', **info})

    return drives
