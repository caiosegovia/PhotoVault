from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from core.database import (
    finish_scan_job,
    get_cached_metadata,
    save_file_record,
    save_source,
    start_scan_job,
)
from core.deduplicator import hash_file_full
from core.metadata import get_media_info
from core.scanner import scan_directory


@dataclass
class InventoryScanResult:
    source_id: int
    job_id: int
    files_seen: int = 0
    files_added: int = 0
    files_changed: int = 0
    files_skipped_cached: int = 0


def scan_inventory_source(
    root_path: Path,
    label: Optional[str] = None,
    source_type: str = 'local',
    role: str = 'origin',
    hash_files: bool = False,
    callback: Optional[Callable[[Path, int], None]] = None,
) -> InventoryScanResult:
    """
    Read-only incremental inventory scan.

    Unchanged files are skipped by path + mtime. Metadata and device origin are
    persisted for new or changed files. Full SHA-256 is optional because it can
    be expensive on external drives.
    """
    label = label or root_path.name or str(root_path)
    source_id = save_source(label, source_type, str(root_path), role=role)
    job_id = start_scan_job(source_id)
    result = InventoryScanResult(source_id=source_id, job_id=job_id)

    try:
        for path in scan_directory(root_path):
            result.files_seen += 1
            if callback:
                callback(path, result.files_seen)

            try:
                stat = path.stat()
            except OSError:
                continue

            cached = get_cached_metadata(str(path), stat.st_mtime)
            if cached:
                result.files_skipped_cached += 1
                continue

            info = get_media_info(path)
            sha256 = hash_file_full(path) if hash_files else None
            save_file_record(
                path=str(path),
                hash_sha256=sha256,
                hash_phash=None,
                date_taken=info.get('date'),
                size=info.get('size', stat.st_size),
                media_type=info.get('type', 'other'),
                extension=info.get('extension', path.suffix.lower()),
                mtime=stat.st_mtime,
                camera_make=info.get('camera_make'),
                camera_model=info.get('camera_model'),
                lens_model=info.get('lens_model'),
                software=info.get('software'),
                device_type=info.get('device_type'),
                device_name=info.get('device_name'),
                origin_hint=info.get('origin_hint'),
                width=info.get('width'),
                height=info.get('height'),
                duration=info.get('duration'),
                has_exif=info.get('has_exif', False),
                source_id=source_id,
            )
            if cached is None:
                result.files_added += 1
            else:
                result.files_changed += 1

        finish_scan_job(
            job_id,
            files_seen=result.files_seen,
            files_added=result.files_added,
            files_changed=result.files_changed,
            status='completed',
        )
    except Exception:
        finish_scan_job(
            job_id,
            files_seen=result.files_seen,
            files_added=result.files_added,
            files_changed=result.files_changed,
            status='error',
        )
        raise

    return result
