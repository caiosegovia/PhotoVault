import hashlib
import shutil
import threading
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Callable

from core.metadata import get_media_date
from core.patterns import apply_pattern
from utils.constants import ALL_MEDIA_EXTENSIONS


@dataclass
class FileOperation:
    src: Path
    dst: Path
    action: str  # 'copy' | 'move' | 'skip'
    status: str = 'pending'  # 'pending' | 'done' | 'error' | 'skipped'
    error: Optional[str] = None


@dataclass
class OrganizationPlan:
    operations: list[FileOperation] = field(default_factory=list)
    destination: Path = None
    pattern: str = ''
    mode: str = 'copy'

    @property
    def total(self):
        return len(self.operations)

    @property
    def conflicts(self):
        return sum(1 for op in self.operations if op.status == 'conflict')


@dataclass
class ExecutionResult:
    total: int = 0
    processed: int = 0
    errors: int = 0
    skipped: int = 0
    operations: list[FileOperation] = field(default_factory=list)


def _resolve_destination(
    src: Path,
    base_dest: Path,
    pattern: str,
    date
) -> Path:
    relative = apply_pattern(pattern, date, src.name)
    return base_dest / relative


def _handle_name_collision(path: Path) -> Path:
    """Add suffix _001, _002, etc. to avoid overwriting."""
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 1
    while True:
        new_name = f"{stem}_{counter:03d}{suffix}"
        new_path = parent / new_name
        if not new_path.exists():
            return new_path
        counter += 1


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def _copy_with_verify(src: Path, dst: Path) -> bool:
    """Copy file and verify hash integrity."""
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        src_hash = _hash_file(src)
        shutil.copy2(src, dst)
        dst_hash = _hash_file(dst)
        return src_hash == dst_hash
    except Exception:
        return False


def _move_with_verify(src: Path, dst: Path) -> bool:
    """Move file with hash verification."""
    try:
        if _copy_with_verify(src, dst):
            src.unlink()
            return True
        return False
    except Exception:
        return False


def _fast_copy(src: Path, dst: Path) -> bool:
    """Copy file without hash verification."""
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        return True
    except Exception:
        return False


def _fast_move(src: Path, dst: Path) -> bool:
    """Move file without hash verification."""
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return True
    except Exception:
        return False


def _execute_op(op: FileOperation, verify: bool) -> None:
    """Execute a single FileOperation, mutating op.status in place."""
    if op.action == 'skip':
        op.status = 'skipped'
        return
    try:
        if verify:
            success = (_copy_with_verify(op.src, op.dst)
                       if op.action == 'copy' else _move_with_verify(op.src, op.dst))
        else:
            success = (_fast_copy(op.src, op.dst)
                       if op.action == 'copy' else _fast_move(op.src, op.dst))
        if success:
            op.status = 'done'
        else:
            op.status = 'error'
            op.error = 'Verificação de hash falhou'
    except Exception as e:
        op.status = 'error'
        op.error = str(e)


def _build_dst_index_cached(destination: Path, skip_existing: bool) -> dict[int, set[str]]:
    """
    Return {size: set_of_sha256} for files already at destination.
    Uses SQLite cache — validates mtime to detect changed/removed files.
    Only files whose size matches a source candidate will be hashed on source side.
    """
    if not skip_existing or not destination.exists():
        return {}

    from core.database import get_destination_records, bulk_save_destination_records, remove_destination_records

    dest_str = str(destination)
    cached = {r['path']: r for r in get_destination_records(dest_str)}

    size_hashes: dict[int, set[str]] = {}
    to_upsert: list[dict] = []
    to_remove: list[str] = []
    disk_paths: set[str] = set()

    try:
        for f in destination.rglob('*'):
            if not f.is_file():
                continue
            fstr = str(f)
            disk_paths.add(fstr)
            try:
                stat = f.stat()
                sz = stat.st_size
                cached_rec = cached.get(fstr)
                if cached_rec and cached_rec['mtime'] == stat.st_mtime and cached_rec['sha256']:
                    sha = cached_rec['sha256']
                else:
                    sha = _hash_file(f)
                    to_upsert.append({'path': fstr, 'size': sz,
                                      'mtime': stat.st_mtime, 'sha256': sha})
                size_hashes.setdefault(sz, set()).add(sha)
            except OSError:
                pass
    except PermissionError:
        pass

    for p in cached:
        if p not in disk_paths:
            to_remove.append(p)

    if to_upsert:
        bulk_save_destination_records(dest_str, to_upsert)
    if to_remove:
        remove_destination_records(dest_str, to_remove)

    return size_hashes


def plan_organization(
    sources: list[Path],
    destination: Path,
    pattern: str,
    mode: str = 'copy',
    extensions=None,
    include_no_date: bool = True,
    skip_existing: bool = False,
    callback: Optional[Callable[[Path, int], None]] = None,
) -> OrganizationPlan:
    """
    Build an OrganizationPlan without executing anything.
    """
    if extensions is None:
        extensions = ALL_MEDIA_EXTENSIONS

    plan = OrganizationPlan(destination=destination, pattern=pattern, mode=mode)
    exts = {e.lower() for e in extensions}
    total = 0

    dst_index = _build_dst_index_cached(destination, skip_existing)

    for source in sources:
        if not source.exists():
            continue
        for src_file in source.rglob('*'):
            if not src_file.is_file():
                continue
            if src_file.suffix.lower() not in exts:
                continue

            total += 1
            if callback:
                callback(src_file, total)

            # Skip if identical content already exists at destination (size pre-filter)
            if dst_index:
                try:
                    sz = src_file.stat().st_size
                    candidates = dst_index.get(sz)
                    if candidates and _hash_file(src_file) in candidates:
                        op = FileOperation(
                            src=src_file,
                            dst=destination / src_file.name,
                            action='skip', status='skipped',
                            error='Já existe no destino'
                        )
                        plan.operations.append(op)
                        continue
                except OSError:
                    pass

            date = get_media_date(src_file)
            if date is None and not include_no_date:
                op = FileOperation(src=src_file, dst=destination / 'sem-data' / src_file.name,
                                   action='skip', status='skipped')
                plan.operations.append(op)
                continue

            if date is None:
                dst = destination / 'sem-data' / src_file.name
            else:
                dst = _resolve_destination(src_file, destination, pattern, date)

            dst = _handle_name_collision(dst)
            op = FileOperation(src=src_file, dst=dst, action=mode)
            plan.operations.append(op)

    return plan


def execute_plan(
    plan: OrganizationPlan,
    callback: Optional[Callable[[int, int, Path, FileOperation], None]] = None,
    workers: int = 1,
    verify: bool = True,
    pause_event: Optional[threading.Event] = None,
    stop_event: Optional[threading.Event] = None,
) -> ExecutionResult:
    """Execute an OrganizationPlan, optionally in parallel."""
    # Pre-sort by destination parent for better disk cache locality
    operations = sorted(plan.operations, key=lambda op: str(op.dst.parent))
    result = ExecutionResult(total=plan.total, operations=plan.operations)

    if workers <= 1:
        for i, op in enumerate(operations):
            if stop_event and stop_event.is_set():
                break
            if pause_event:
                pause_event.wait()
            if callback:
                callback(i, plan.total, op.src, op)
            _execute_op(op, verify)
            if op.status == 'done':
                result.processed += 1
            elif op.status == 'skipped':
                result.skipped += 1
            else:
                result.errors += 1
    else:
        lock = threading.Lock()
        completed = [0]

        def run_op(op: FileOperation):
            if stop_event and stop_event.is_set():
                return
            if pause_event:
                pause_event.wait()
            if stop_event and stop_event.is_set():
                return
            # Capture size before operation (src may be deleted on move)
            try:
                op._pre_size = op.src.stat().st_size
            except OSError:
                op._pre_size = 0
            _execute_op(op, verify)
            with lock:
                idx = completed[0]
                completed[0] += 1
                if op.status == 'done':
                    result.processed += 1
                elif op.status == 'skipped':
                    result.skipped += 1
                else:
                    result.errors += 1
            if callback:
                callback(idx, plan.total, op.src, op)

        max_pending = max(workers * 2, workers)
        op_iter = iter(operations)
        pending = set()
        with ThreadPoolExecutor(max_workers=workers) as executor:
            while True:
                if stop_event and stop_event.is_set():
                    break
                while len(pending) < max_pending:
                    try:
                        op = next(op_iter)
                    except StopIteration:
                        break
                    pending.add(executor.submit(run_op, op))
                if not pending:
                    break
                done, pending = wait(pending, return_when=FIRST_COMPLETED)
                for future in done:
                    try:
                        future.result()
                    except Exception:
                        pass

    return result


def apply_duplicate_decisions(
    plan: OrganizationPlan,
    duplicate_groups: dict[str, list[Path]],
    decisions: dict[str, str],
) -> int:
    """
    Apply duplicate review choices to a plan.

    decisions maps duplicate group keys to either a keeper path string or '__all__'.
    Returns the number of operations changed to skip.
    """
    if not decisions:
        return 0

    skip_paths: set[Path] = set()
    for group_key, decision in decisions.items():
        if decision == '__all__':
            continue
        group = duplicate_groups.get(group_key)
        if not group:
            continue
        keeper = Path(decision)
        for path in group:
            if path != keeper:
                skip_paths.add(path)

    if not skip_paths:
        return 0

    changed = 0
    for op in plan.operations:
        if op.src in skip_paths and op.action != 'skip':
            op.action = 'skip'
            op.status = 'skipped'
            op.error = 'Duplicata marcada para ignorar'
            changed += 1

    return changed
