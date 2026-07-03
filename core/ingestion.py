import shutil
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from core.database import (
    add_ingest_operation,
    create_ingest_plan,
    get_asset_by_sha256,
    get_asset_instances,
    get_import_by_plan,
    get_ingest_operations,
    save_asset_instance,
    save_audit_event,
    save_source,
    save_vault,
    update_import_file_status,
    update_import_status,
    update_import_summary,
    update_ingest_operation_status,
    update_ingest_plan_status,
    upsert_asset,
)
from core.deduplicator import hash_file_full
from core.identity import MediaIdentity, identity_to_asset, identify_media
from core.scanner import scan_directory
from core.vault import VaultConfig, canonical_path


log = logging.getLogger(__name__)


@dataclass
class IngestPlanResult:
    plan_id: int
    vault: VaultConfig
    operations: list[dict] = field(default_factory=list)
    scanned: int = 0
    copied: int = 0
    skipped: int = 0
    errors: int = 0

    @property
    def total(self) -> int:
        return len(self.operations)


def ensure_vault(root_path: Path, pattern: str = '{year}/{month:02d}',
                 label: str = 'Galeria PhotoVault') -> VaultConfig:
    """Create or update the fixed destination vault."""
    vault_id = save_vault(label, str(root_path), pattern)
    save_source(label, 'destination', str(root_path), role='destination')
    return VaultConfig(id=vault_id, label=label, root_path=root_path, pattern=pattern)


def _has_destination_instance(asset_id: int) -> bool:
    return any(row['role'] == 'destination' for row in get_asset_instances(asset_id))


def _persist_identity(identity: MediaIdentity, source_id: int, role: str) -> int:
    asset_id = upsert_asset(identity_to_asset(identity))
    save_asset_instance(
        asset_id=asset_id,
        source_id=source_id,
        path=str(identity.path),
        role=role,
        quality_score=identity.quality_score,
    )
    return asset_id


def build_ingest_plan(
    sources: list[Path],
    vault_root: Path,
    pattern: str = '{year}/{month:02d}',
    mode: str = 'copy',
    callback: Optional[Callable[[Path, int], None]] = None,
) -> IngestPlanResult:
    """
    Inventory sources, create logical assets, and persist a resumable ingest plan.

    Duplicate decisions are global within the plan and against known destination
    instances. The function is read-only toward source and destination files.
    """
    vault = ensure_vault(vault_root, pattern)
    log.info("build_ingest_plan start vault=%s sources=%s mode=%s", vault_root, sources, mode)
    result = IngestPlanResult(
        plan_id=create_ingest_plan(vault.id, mode=mode, summary={'sources': [str(s) for s in sources]}),
        vault=vault,
    )
    planned_hashes: set[str] = set()
    scan_roots: list[Path] = []
    seen_roots: set[str] = set()

    for source in sources:
        key = str(source.resolve()).lower() if source.exists() else str(source).lower()
        if key not in seen_roots:
            scan_roots.append(source)
            seen_roots.add(key)

    for source in scan_roots:
        if not source.exists():
            log.warning("build_ingest_plan source_missing path=%s", source)
            continue
        role = 'destination' if source.resolve() == vault_root.resolve() else 'origin'
        source_id = save_source(source.name or str(source), 'local', str(source), role=role)
        log.info("build_ingest_plan scanning source=%s role=%s", source, role)

        for path in scan_directory(source):
            result.scanned += 1
            if callback:
                callback(path, result.scanned)

            identity = identify_media(path)
            if identity is None:
                result.errors += 1
                log.warning("build_ingest_plan identity_failed path=%s", path)
                continue

            asset_id = _persist_identity(identity, source_id, role)
            dst = canonical_path(vault, identity)
            existing_asset = get_asset_by_sha256(identity.sha256)
            has_destination = _has_destination_instance(asset_id)

            if role == 'destination':
                action = 'skip'
                reason = 'already_in_vault'
            elif has_destination:
                action = 'skip'
                reason = 'exact_duplicate_in_vault'
            elif identity.sha256 in planned_hashes:
                action = 'skip'
                reason = 'exact_duplicate_in_plan'
            elif existing_asset and has_destination:
                action = 'skip'
                reason = 'known_asset_in_vault'
            else:
                action = mode
                reason = 'new_asset'
                planned_hashes.add(identity.sha256)

            operation = {
                'asset_id': asset_id,
                'src_path': str(path),
                'dst_path': str(dst),
                'action': action,
                'reason': reason,
                'status': 'skipped' if action == 'skip' else 'planned',
                'sha256': identity.sha256,
                'size': identity.size,
            }
            operation_id = add_ingest_operation(result.plan_id, operation)
            operation['id'] = operation_id
            result.operations.append(operation)
            if action == 'skip':
                result.skipped += 1

            if result.scanned % 100 == 0:
                log.info(
                    "build_ingest_plan progress scanned=%s ops=%s skipped=%s errors=%s source=%s",
                    result.scanned,
                    len(result.operations),
                    result.skipped,
                    result.errors,
                    source,
                )

    save_audit_event(
        'ingest_plan',
        result.plan_id,
        'created',
        'Plano de ingestao criado',
        {'scanned': result.scanned, 'operations': len(result.operations)},
    )
    log.info(
        "build_ingest_plan done plan_id=%s scanned=%s ops=%s skipped=%s errors=%s",
        result.plan_id,
        result.scanned,
        len(result.operations),
        result.skipped,
        result.errors,
    )
    return result


def _copy_with_staging(src: Path, dst: Path, expected_sha256: Optional[str]) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    staging = dst.with_name(f".{dst.name}.photovault-part")
    if staging.exists():
        staging.unlink()
    shutil.copy2(src, staging)
    actual = hash_file_full(staging)
    if expected_sha256 and actual != expected_sha256:
        try:
            staging.unlink()
        except OSError:
            pass
        raise IOError('Verificacao de hash falhou')
    staging.replace(dst)


def execute_ingest_plan(
    plan_id: int,
    callback: Optional[Callable[[int, int, Path], None]] = None,
) -> dict:
    """Execute persisted ingest operations with staging and hash verification."""
    update_ingest_plan_status(plan_id, 'running')
    import_row = get_import_by_plan(plan_id)
    import_id = int(import_row['id']) if import_row else None
    if import_id:
        update_import_status(import_id, 'running')
    log.info("execute_ingest_plan start plan_id=%s", plan_id)
    operations = get_ingest_operations(plan_id)
    stats = {'total': len(operations), 'processed': 0, 'skipped': 0, 'errors': 0, 'bytes_imported': 0}

    try:
        for index, op in enumerate(operations):
            src = Path(op['src_path'])
            dst = Path(op['dst_path'])
            if callback:
                callback(index, len(operations), src)

            if op['action'] == 'skip':
                update_ingest_operation_status(op['id'], 'skipped')
                if import_id:
                    update_import_file_status(import_id, op['src_path'], 'skipped')
                stats['skipped'] += 1
                continue

            update_ingest_operation_status(op['id'], 'running')
            if import_id:
                update_import_file_status(import_id, op['src_path'], 'running')
            try:
                _copy_with_staging(src, dst, op['sha256'])
                if op['action'] == 'move':
                    src.unlink()
                if op['asset_id']:
                    save_asset_instance(
                        asset_id=op['asset_id'],
                        path=str(dst),
                        role='destination',
                        quality_score=0,
                    )
                update_ingest_operation_status(op['id'], 'done')
                if import_id:
                    update_import_file_status(import_id, op['src_path'], 'done')
                stats['processed'] += 1
                stats['bytes_imported'] += op['size'] or 0
            except Exception as exc:
                log.exception("execute_ingest_plan operation_failed id=%s src=%s dst=%s", op['id'], src, dst)
                update_ingest_operation_status(op['id'], 'error', str(exc))
                if import_id:
                    update_import_file_status(import_id, op['src_path'], 'error', str(exc))
                stats['errors'] += 1

        update_ingest_plan_status(plan_id, 'completed' if stats['errors'] == 0 else 'error')
        if import_id:
            update_import_summary(import_id, {
                'files_imported': stats['processed'],
                'files_skipped': stats['skipped'],
                'files_error': stats['errors'],
                'bytes_imported': stats['bytes_imported'],
            })
            update_import_status(import_id, 'completed' if stats['errors'] == 0 else 'failed')
    except Exception:
        log.exception("execute_ingest_plan fatal plan_id=%s", plan_id)
        update_ingest_plan_status(plan_id, 'error')
        if import_id:
            update_import_status(import_id, 'failed')
        raise

    save_audit_event('ingest_plan', plan_id, 'executed', 'Plano de ingestao executado', stats)
    log.info("execute_ingest_plan done plan_id=%s stats=%s", plan_id, stats)
    return stats
