import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from core.database import (
    add_import_file,
    add_ingest_operation,
    create_import,
    create_ingest_plan,
    get_asset_by_sha256,
    get_asset_instances,
    get_import,
    get_import_files,
    save_asset_instance,
    save_asset_metadata,
    save_audit_event,
    save_source,
    set_import_plan,
    set_ingest_plan_import,
    update_import_status,
    update_import_summary,
    upsert_asset,
)
from core.identity import MediaIdentity, identify_media, identity_to_asset
from core.ingestion import ensure_vault
from core.safety import validate_import_paths
from core.scanner import ScanReport, scan_directory
from core.vault import VaultConfig, canonical_path


log = logging.getLogger(__name__)


@dataclass
class ImportAnalysis:
    import_id: int
    plan_id: int
    vault: VaultConfig
    name: str
    source_path: Path
    operations: list[dict] = field(default_factory=list)
    files_found: int = 0
    files_new: int = 0
    files_duplicate: int = 0
    files_existing: int = 0
    files_review: int = 0
    bytes_found: int = 0
    bytes_new: int = 0
    errors: int = 0

    @property
    def total(self) -> int:
        return len(self.operations)


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
    save_asset_metadata(
        asset_id=asset_id,
        path=str(identity.path),
        extractor='photovault-identity',
        mtime=identity.path.stat().st_mtime,
        raw={
            'sha256': identity.sha256,
            'size': identity.size,
            'media_type': identity.media_type,
            'extension': identity.extension,
            'date_taken': identity.date_taken,
            'width': identity.width,
            'height': identity.height,
            'duration': identity.duration,
            'has_exif': identity.has_exif,
            'device_name': identity.device_name,
            'quality_score': identity.quality_score,
        },
    )
    return asset_id


def _default_import_name(source_path: Path) -> str:
    return source_path.name or str(source_path)


def create_import_analysis(
    source_path: Path,
    vault_root: Path,
    pattern: str = '{year}/{month:02d}',
    mode: str = 'copy',
    name: Optional[str] = None,
    callback: Optional[Callable[[Path, int], None]] = None,
) -> ImportAnalysis:
    """Analyze one source folder as an auditable import into a permanent vault."""
    if not source_path.exists():
        raise FileNotFoundError(f'Origem nao encontrada: {source_path}')
    validate_import_paths(source_path, vault_root)

    vault = ensure_vault(vault_root, pattern)
    import_name = name or _default_import_name(source_path)
    import_id = create_import(
        vault.id,
        import_name,
        str(source_path),
        status='scanning',
        summary={'mode': mode, 'pattern': pattern},
    )
    plan_id = create_ingest_plan(
        vault.id,
        mode=mode,
        summary={'import_id': import_id, 'source': str(source_path), 'name': import_name},
    )
    set_import_plan(import_id, plan_id)
    set_ingest_plan_import(plan_id, import_id)

    analysis = ImportAnalysis(
        import_id=import_id,
        plan_id=plan_id,
        vault=vault,
        name=import_name,
        source_path=source_path,
    )
    planned_hashes: set[str] = set()
    source_id = save_source(import_name, 'local', str(source_path), role='origin')
    log.info("import analysis start import_id=%s source=%s vault=%s", import_id, source_path, vault_root)

    try:
        scan_report = ScanReport()
        for path in scan_directory(source_path, report=scan_report):
            analysis.files_found += 1
            if callback:
                callback(path, analysis.files_found)

            identity = identify_media(path)
            if identity is None:
                analysis.errors += 1
                add_import_file(import_id, {
                    'src_path': str(path),
                    'status': 'error',
                    'decision': 'skip',
                    'reason': 'metadata_error',
                    'error': 'Falha ao identificar midia',
                })
                continue

            analysis.bytes_found += identity.size
            asset_id = _persist_identity(identity, source_id, 'origin')
            dst = canonical_path(vault, identity)
            existing_asset = get_asset_by_sha256(identity.sha256)
            has_destination = _has_destination_instance(asset_id)

            if has_destination:
                action = 'skip'
                reason = 'exact_duplicate_in_vault'
                analysis.files_duplicate += 1
            elif identity.sha256 in planned_hashes:
                action = 'skip'
                reason = 'exact_duplicate_in_plan'
                analysis.files_duplicate += 1
            elif existing_asset and has_destination:
                action = 'skip'
                reason = 'known_asset_in_vault'
                analysis.files_duplicate += 1
            else:
                action = mode
                reason = 'new_asset'
                planned_hashes.add(identity.sha256)
                analysis.files_new += 1
                analysis.bytes_new += identity.size

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
            operation_id = add_ingest_operation(plan_id, operation)
            operation['id'] = operation_id
            analysis.operations.append(operation)
            add_import_file(import_id, {
                'ingest_operation_id': operation_id,
                'asset_id': asset_id,
                'src_path': str(path),
                'dst_path': str(dst),
                'sha256': identity.sha256,
                'status': operation['status'],
                'decision': action,
                'reason': reason,
                'size': identity.size,
                'media_type': identity.media_type,
                'extension': identity.extension,
                'date_taken': identity.date_taken,
            })

            if analysis.files_found % 100 == 0:
                log.info(
                    "import analysis progress import_id=%s files=%s new=%s duplicates=%s errors=%s",
                    import_id,
                    analysis.files_found,
                    analysis.files_new,
                    analysis.files_duplicate,
                    analysis.errors,
                )

        analysis.errors += len(scan_report.errors)
        summary = import_summary_from_analysis(analysis)
        if scan_report.errors:
            summary['summary']['scan_errors'] = scan_report.errors[:100]
        update_import_summary(import_id, summary)
        update_import_status(import_id, 'analyzed')
        save_audit_event(
            'import',
            import_id,
            'analyzed',
            'Importacao analisada',
            summary,
        )
        log.info("import analysis done import_id=%s summary=%s", import_id, summary)
        return analysis
    except Exception:
        update_import_status(import_id, 'failed')
        log.exception("import analysis failed import_id=%s", import_id)
        raise


def import_summary_from_analysis(analysis: ImportAnalysis) -> dict:
    skipped = analysis.files_duplicate + analysis.files_existing
    return {
        'files_found': analysis.files_found,
        'files_new': analysis.files_new,
        'files_duplicate': analysis.files_duplicate,
        'files_existing': analysis.files_existing,
        'files_review': analysis.files_review,
        'files_skipped': skipped,
        'files_error': analysis.errors,
        'bytes_found': analysis.bytes_found,
        'bytes_new': analysis.bytes_new,
        'summary': {
            'name': analysis.name,
            'source_path': str(analysis.source_path),
            'plan_id': analysis.plan_id,
        },
    }


def load_import_analysis(import_id: int) -> Optional[ImportAnalysis]:
    row = get_import(import_id)
    if not row:
        return None
    files = get_import_files(import_id, limit=5000)
    operations = [
        {
            'id': item.get('ingest_operation_id'),
            'asset_id': item.get('asset_id'),
            'src_path': item.get('src_path'),
            'dst_path': item.get('dst_path'),
            'action': item.get('decision'),
            'reason': item.get('reason'),
            'status': item.get('status'),
            'sha256': item.get('sha256'),
            'size': item.get('size'),
        }
        for item in files
    ]
    vault = VaultConfig(
        id=int(row['vault_id']),
        label='Galeria PhotoVault',
        root_path=Path(''),
        pattern='{year}/{month:02d}',
    )
    return ImportAnalysis(
        import_id=int(row['id']),
        plan_id=int(row['ingest_plan_id'] or 0),
        vault=vault,
        name=row['name'],
        source_path=Path(row['source_path']),
        operations=operations,
        files_found=row['files_found'] or len(files),
        files_new=row['files_new'] or 0,
        files_duplicate=row['files_duplicate'] or 0,
        files_existing=row['files_existing'] or 0,
        files_review=row['files_review'] or 0,
        bytes_found=row['bytes_found'] or 0,
        bytes_new=row['bytes_new'] or 0,
        errors=row['files_error'] or 0,
    )
