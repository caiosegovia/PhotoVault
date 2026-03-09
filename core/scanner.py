from pathlib import Path
from typing import Iterator, Callable, Optional, Set

from utils.constants import ALL_MEDIA_EXTENSIONS, PHOTO_EXTENSIONS, VIDEO_EXTENSIONS


def scan_directory(
    path: Path,
    extensions: Optional[Set[str]] = None,
    recursive: bool = True,
    callback: Optional[Callable[[Path, int], None]] = None
) -> Iterator[Path]:
    """
    Discover media files in directory.
    callback(current_file, total_found) is called for each file found.
    """
    if extensions is None:
        extensions = ALL_MEDIA_EXTENSIONS

    exts_lower = {e.lower() for e in extensions}
    total_found = 0

    try:
        if recursive:
            iterator = path.rglob('*')
        else:
            iterator = path.glob('*')

        for item in iterator:
            if item.is_file() and item.suffix.lower() in exts_lower:
                total_found += 1
                if callback:
                    callback(item, total_found)
                yield item
    except PermissionError:
        pass


def count_files(path: Path, extensions: Optional[Set[str]] = None) -> dict:
    """Count files by type in directory."""
    if extensions is None:
        extensions = ALL_MEDIA_EXTENSIONS

    total = 0
    photos = 0
    videos = 0
    others = 0
    size_bytes = 0
    photos_size = 0
    videos_size = 0
    others_size = 0

    try:
        for item in path.rglob('*'):
            if not item.is_file():
                continue
            ext = item.suffix.lower()
            if ext not in extensions:
                continue
            total += 1
            try:
                s = item.stat().st_size
                size_bytes += s
            except OSError:
                s = 0

            if ext in PHOTO_EXTENSIONS:
                photos += 1
                photos_size += s
            elif ext in VIDEO_EXTENSIONS:
                videos += 1
                videos_size += s
            else:
                others += 1
                others_size += s
    except PermissionError:
        pass

    return {
        'total': total,
        'photos': photos,
        'videos': videos,
        'others': others,
        'size_bytes': size_bytes,
        'photos_size': photos_size,
        'videos_size': videos_size,
        'others_size': others_size,
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
