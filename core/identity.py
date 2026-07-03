from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core.deduplicator import hash_file_full
from core.metadata import get_media_info


@dataclass(frozen=True)
class MediaIdentity:
    path: Path
    sha256: str
    size: int
    media_type: str
    extension: str
    date_taken: object = None
    width: Optional[int] = None
    height: Optional[int] = None
    duration: Optional[float] = None
    has_exif: bool = False
    device_name: Optional[str] = None
    quality_score: int = 0


def score_media_quality(info: dict) -> int:
    """Score a file for keeper decisions without making destructive choices."""
    score = 0
    if info.get('has_exif'):
        score += 1000
    width = info.get('width') or 0
    height = info.get('height') or 0
    if width and height:
        score += min((width * height) // 1_000_000, 200)
    if info.get('duration'):
        score += 50
    if info.get('device_name') and info.get('device_name') != 'Desconhecido':
        score += 25
    score += min((info.get('size') or 0) // (10 * 1024 * 1024), 100)
    return int(score)


def identify_media(path: Path) -> Optional[MediaIdentity]:
    """Return the content identity and useful metadata for a media file."""
    try:
        info = get_media_info(path)
    except Exception:
        return None

    sha256 = hash_file_full(path)
    if not sha256:
        return None

    return MediaIdentity(
        path=path,
        sha256=sha256,
        size=info.get('size') or path.stat().st_size,
        media_type=info.get('type', 'other'),
        extension=info.get('extension') or path.suffix.lower(),
        date_taken=info.get('date'),
        width=info.get('width'),
        height=info.get('height'),
        duration=info.get('duration'),
        has_exif=bool(info.get('has_exif')),
        device_name=info.get('device_name'),
        quality_score=score_media_quality(info),
    )


def identity_to_asset(identity: MediaIdentity) -> dict:
    """Convert a MediaIdentity to the database asset shape."""
    return {
        'sha256': identity.sha256,
        'size': identity.size,
        'media_type': identity.media_type,
        'extension': identity.extension,
        'date_taken': identity.date_taken,
        'width': identity.width,
        'height': identity.height,
        'duration': identity.duration,
    }
