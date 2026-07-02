import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Callable

from utils.constants import PHOTO_EXTENSIONS, PARTIAL_HASH_CHUNK


@dataclass
class DuplicateResult:
    exact: dict[str, list[Path]] = field(default_factory=dict)
    visual: dict[str, list[Path]] = field(default_factory=dict)
    space_wasted: int = 0


def hash_file_partial(path: Path, chunk_size: int = PARTIAL_HASH_CHUNK) -> Optional[str]:
    """SHA-256 of first chunk_size bytes."""
    h = hashlib.sha256()
    try:
        with open(path, 'rb') as f:
            h.update(f.read(chunk_size))
    except OSError:
        return None
    return h.hexdigest()


def hash_file_full(path: Path) -> Optional[str]:
    """Full SHA-256 hash of file."""
    h = hashlib.sha256()
    try:
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()


def compute_phash(path: Path) -> Optional[str]:
    """Compute perceptual hash for images. Returns None for non-images."""
    if path.suffix.lower() not in PHOTO_EXTENSIONS:
        return None
    try:
        import imagehash
        from PIL import Image
        img = Image.open(path).convert('RGB')
        return str(imagehash.phash(img))
    except Exception:
        return None


def find_exact_duplicates(
    paths: list[Path],
    callback: Optional[Callable[[int, int], None]] = None
) -> dict[str, list[Path]]:
    """
    4-layer duplicate detection:
    1. Group by size
    2. Partial hash
    3. Full hash
    Returns {sha256: [path1, path2, ...]} for groups with >1 file.
    """
    total = len(paths)

    # Layer 1: group by size
    by_size: dict[int, list[Path]] = {}
    for i, p in enumerate(paths):
        if callback:
            callback(i, total)
        try:
            size = p.stat().st_size
        except OSError:
            continue
        by_size.setdefault(size, []).append(p)

    candidates = [group for group in by_size.values() if len(group) > 1]

    # Layer 2: partial hash
    by_partial: dict[str, list[Path]] = {}
    for group in candidates:
        for p in group:
            ph = hash_file_partial(p)
            if ph is None:
                continue
            by_partial.setdefault(ph, []).append(p)

    candidates2 = [g for g in by_partial.values() if len(g) > 1]

    # Layer 3: full hash
    by_full: dict[str, list[Path]] = {}
    for group in candidates2:
        for p in group:
            fh = hash_file_full(p)
            if fh is None:
                continue
            by_full.setdefault(fh, []).append(p)

    return {h: g for h, g in by_full.items() if len(g) > 1}


def find_visual_duplicates(
    paths: list[Path],
    threshold: int = 10,
    callback: Optional[Callable[[int, int], None]] = None
) -> dict[str, list[Path]]:
    """
    Find visually similar images using pHash.
    Returns {phash_repr: [path1, path2, ...]} for similar groups.
    """
    import imagehash

    photo_paths = [p for p in paths if p.suffix.lower() in PHOTO_EXTENSIONS]
    hashes: list[tuple[Path, imagehash.ImageHash]] = []

    for i, p in enumerate(photo_paths):
        if callback:
            callback(i, len(photo_paths))
        ph_str = compute_phash(p)
        if ph_str is None:
            continue
        try:
            ph = imagehash.hex_to_hash(ph_str)
            hashes.append((p, ph))
        except Exception:
            continue

    # Group by similarity
    groups: list[list[Path]] = []
    used = set()
    for i, (p1, h1) in enumerate(hashes):
        if i in used:
            continue
        group = [p1]
        for j, (p2, h2) in enumerate(hashes):
            if j <= i or j in used:
                continue
            if abs(h1 - h2) <= threshold:
                group.append(p2)
                used.add(j)
        if len(group) > 1:
            used.add(i)
            groups.append(group)

    # Build result dict keyed by the representative phash of group[0]
    result = {}
    hash_map = {p: h for p, h in hashes}
    for group in groups:
        key = str(hash_map.get(group[0], group[0].name))
        result[key] = group
    return result


def _visual_groups_safe(
    paths: list[Path],
    threshold: int,
    callback: Optional[Callable]
) -> dict[str, list[Path]]:
    """Safe wrapper for visual duplicates that handles import errors."""
    try:
        return find_visual_duplicates(paths, threshold, callback)
    except Exception:
        return {}


def find_all_duplicates(
    paths: list[Path],
    threshold: int = 10,
    callback: Optional[Callable[[str, int, int], None]] = None
) -> DuplicateResult:
    """
    Run all duplicate detection layers.
    callback(stage, current, total) for progress updates.
    """
    result = DuplicateResult()

    def exact_cb(cur, tot):
        if callback:
            callback('exact', cur, tot)

    result.exact = find_exact_duplicates(paths, exact_cb)

    # Calculate space wasted by exact duplicates
    for group in result.exact.values():
        if len(group) > 1:
            try:
                keeper_size = group[0].stat().st_size
                for dup in group[1:]:
                    result.space_wasted += dup.stat().st_size
            except OSError:
                pass

    def visual_cb(cur, tot):
        if callback:
            callback('visual', cur, tot)

    result.visual = _visual_groups_safe(paths, threshold, visual_cb)

    return result


def suggest_keeper(paths: list[Path]) -> Path:
    """
    Suggest which file to keep from a duplicate group.
    Heuristic: largest size > has EXIF > shorter name > oldest mtime.
    """
    from core.metadata import _extract_photo_date

    def score(p: Path):
        try:
            size = p.stat().st_size
            mtime = p.stat().st_mtime
        except OSError:
            size = 0
            mtime = float('inf')

        has_exif = _extract_photo_date(p) is not None if p.suffix.lower() in PHOTO_EXTENSIONS else False
        name_len = len(p.stem)
        return (-size, not has_exif, name_len, mtime)

    return min(paths, key=score)
