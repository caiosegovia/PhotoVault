import argparse
import json
import logging
import shutil
import sys
import time
from pathlib import Path

from core.database import (
    backfill_catalog_metadata_from_gallery,
    gallery_breakdowns,
    gallery_totals,
    get_import_files,
    get_latest_vault,
    init_db,
    list_gallery_assets,
    list_imports,
    save_vault,
    summarize_import_decisions,
    update_import_file_decision,
)
from core.imports import create_import_analysis
from core.ingestion import execute_ingest_plan
from core.metadata_enrichment import enrich_gallery_metadata
from core.patterns import validate_pattern
from core.safety import validate_import_paths, validate_reset_root
from core.runtime_tools import exiftool_version, has_exiftool, has_ffmpeg
from core.thumbnail_cache import ensure_thumbnail, get_cached_thumbnail
from utils.constants import CONFIG_DIR
from utils.formatting import format_size
from utils.logging import get_log_path, setup_logging


PROGRESS_PATH = CONFIG_DIR / "progress.json"
GALLERY_ITEM_LIMIT = 50000
log = logging.getLogger("photovault.bridge")

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


def _print(data: dict) -> None:
    sys.stdout.write(json.dumps(data, ensure_ascii=True, default=str))
    sys.stdout.flush()


def _read_payload() -> dict:
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}


def _write_progress(stage: str, message: str, current: int = 0, total: int = 0,
                    path: str = "", status: str = "running", metrics: dict | None = None) -> None:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            'stage': stage,
            'message': message,
            'current': current,
            'total': total,
            'path': path,
            'status': status,
            'updatedAt': time.time(),
            'logPath': str(get_log_path()),
        }
        if metrics:
            payload['metrics'] = metrics
        PROGRESS_PATH.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
    except OSError:
        log.warning("progress write failed stage=%s", stage)


def _progress_payload() -> dict:
    if not PROGRESS_PATH.exists():
        return {
            'stage': 'idle',
            'message': 'Sem processo em andamento.',
            'current': 0,
            'total': 0,
            'path': '',
            'status': 'idle',
            'updatedAt': None,
            'logPath': str(get_log_path()),
        }
    try:
        return json.loads(PROGRESS_PATH.read_text(encoding='utf-8'))
    except Exception:
        return {
            'stage': 'unknown',
            'message': 'Nao consegui ler o progresso.',
            'current': 0,
            'total': 0,
            'path': '',
            'status': 'unknown',
            'updatedAt': None,
            'logPath': str(get_log_path()),
        }


def _tail_log(lines: int = 120) -> list[str]:
    path = get_log_path()
    if not path.exists():
        return []
    try:
        content = path.read_text(encoding='utf-8', errors='replace').splitlines()
        return content[-lines:]
    except Exception:
        return []


def _status(value: str) -> str:
    return {
        'created': 'ready',
        'scanning': 'running',
        'analyzed': 'ready',
        'running': 'running',
        'completed': 'done',
        'failed': 'failed',
        'cancelled': 'failed',
    }.get(value or '', 'ready')


def _decision(value: str, reason: str) -> str:
    if value in {'copy', 'move', 'import'}:
        return 'import'
    if reason == 'new_asset':
        return 'import'
    if value == 'review':
        return 'review'
    return 'skip'


def _file_status(reason: str, status: str) -> str:
    if status == 'error' or reason == 'metadata_error':
        return 'Erro'
    if reason == 'new_asset':
        return 'Novo'
    if reason in {'exact_duplicate_in_plan', 'exact_duplicate_in_vault', 'known_asset_in_vault'}:
        return 'Duplicata'
    return 'Revisão'


def _import_row(row: dict) -> dict:
    return {
        'id': row['id'],
        'name': row['name'],
        'status': _status(row.get('status')),
        'rawStatus': row.get('status'),
        'date': (row.get('created_at') or '')[:16].replace('T', ' '),
        'source': row.get('source_path') or '',
        'found': row.get('files_found') or 0,
        'fresh': row.get('files_new') or 0,
        'duplicates': row.get('files_duplicate') or 0,
        'errors': row.get('files_error') or 0,
        'bytes': format_size(row.get('bytes_new') or 0),
        'bytesNew': row.get('bytes_new') or 0,
        'planId': row.get('ingest_plan_id'),
    }


def _gallery_row(row: dict, include_thumb: bool = True) -> dict:
    path = Path(row.get('path') or '')
    thumb = get_cached_thumbnail(path) if include_thumb and path.exists() else None
    media_type = row.get('media_type') or 'other'
    extension = row.get('extension') or path.suffix.lower()
    ffmpeg_available = has_ffmpeg()
    preview_status = 'ready' if thumb else 'missing'
    if thumb and media_type == 'video' and not ffmpeg_available:
        preview_status = 'placeholder'
    return {
        'id': row.get('instance_id'),
        'assetId': row.get('asset_id'),
        'name': path.name,
        'path': str(path),
        'thumbnail': str(thumb) if thumb else '',
        'previewStatus': preview_status,
        'mediaType': media_type,
        'extension': extension,
        'size': format_size(row.get('size') or 0),
        'sizeBytes': row.get('size') or 0,
        'date': (row.get('date_taken') or 'sem data')[:10],
        'resolution': (
            f"{row.get('width')}x{row.get('height')}"
            if row.get('width') and row.get('height')
            else 'sem dimensoes'
        ),
        'deviceName': row.get('device_name') or 'Desconhecido',
        'deviceType': row.get('device_type') or 'unknown',
        'cameraMake': row.get('camera_make') or '',
        'cameraModel': row.get('camera_model') or '',
        'qualityScore': row.get('quality_score') or 0,
    }


def _bucket(row: dict) -> dict:
    return {
        'label': row.get('label') or '',
        'count': row.get('count') or 0,
        'bytes': format_size(row.get('bytes') or 0),
        'bytesRaw': row.get('bytes') or 0,
    }


def _reason_label(value: str) -> str:
    return {
        'new_asset': 'Novos para importar',
        'exact_duplicate_in_plan': 'Duplicados nesta origem',
        'exact_duplicate_in_vault': 'Ja existem no vault',
        'known_asset_in_vault': 'Conhecidos no vault',
        'metadata_error': 'Erro de metadados',
    }.get(value or '', value or 'Sem motivo')


def _import_insights(import_id: int | None) -> dict:
    if not import_id:
        return {'reasonGroups': [], 'mediaGroups': [], 'statusGroups': []}
    summary = summarize_import_decisions(import_id)
    reason_groups = []
    for row in summary['reasonGroups']:
        reason = row.get('label') or ''
        reason_groups.append({
            'reason': reason,
            'label': _reason_label(reason),
            'decision': _decision(row.get('decision'), reason),
            'mediaType': row.get('media_type') or 'media',
            'status': row.get('status') or 'planned',
            'count': row.get('count') or 0,
            'bytes': format_size(row.get('bytes') or 0),
            'bytesRaw': row.get('bytes') or 0,
        })
    return {
        'reasonGroups': reason_groups,
        'mediaGroups': [_bucket(row) for row in summary['mediaGroups']],
        'statusGroups': [_bucket(row) for row in summary['statusGroups']],
    }


def _gallery_payload(limit: int = GALLERY_ITEM_LIMIT) -> dict:
    started = time.perf_counter()
    backfilled = backfill_catalog_metadata_from_gallery()
    backfill_at = time.perf_counter()
    gallery_total = gallery_totals()
    totals_at = time.perf_counter()
    breakdowns = gallery_breakdowns()
    breakdowns_at = time.perf_counter()
    assets = list_gallery_assets(limit)
    assets_at = time.perf_counter()
    return {
        'items': [_gallery_row(item) for item in assets],
        'total': gallery_total['total'],
        'photos': gallery_total['photos'],
        'videos': gallery_total['videos'],
        'withoutDate': gallery_total['without_date'],
        'bytes': format_size(gallery_total['bytes_total']),
        'bytesTotal': gallery_total['bytes_total'],
        'firstDate': (gallery_total.get('first_date') or '')[:10],
        'lastDate': (gallery_total.get('last_date') or '')[:10],
        'yearCount': gallery_total.get('year_count') or 0,
        'monthCount': gallery_total.get('month_count') or 0,
        'extensionCount': gallery_total.get('extension_count') or 0,
        'breakdowns': {
            'media': [_bucket(row) for row in breakdowns['media']],
            'years': [_bucket(row) for row in breakdowns['years']],
            'months': [_bucket(row) for row in breakdowns['months']],
            'extensions': [_bucket(row) for row in breakdowns['extensions']],
            'devices': [_bucket(row) for row in breakdowns.get('devices', [])],
            'deviceTypes': [_bucket(row) for row in breakdowns.get('deviceTypes', [])],
            'cameras': [_bucket(row) for row in breakdowns.get('cameras', [])],
        },
        'capabilities': {
            'ffmpegAvailable': has_ffmpeg(),
            'exiftoolAvailable': has_exiftool(),
            'exiftoolVersion': exiftool_version(),
        },
        'timings': {
            'backfillCount': backfilled,
            'backfillSeconds': backfill_at - started,
            'totalsSeconds': totals_at - backfill_at,
            'breakdownsSeconds': breakdowns_at - totals_at,
            'assetsSeconds': assets_at - breakdowns_at,
            'totalSeconds': time.perf_counter() - started,
        },
    }


def _file_row(row: dict) -> dict:
    return {
        'id': row['id'],
        'status': _file_status(row.get('reason'), row.get('status')),
        'source': row.get('src_path') or '',
        'destination': row.get('dst_path') or '',
        'size': format_size(row.get('size') or 0),
        'sizeBytes': row.get('size') or 0,
        'device': row.get('media_type') or 'mídia',
        'date': (row.get('date_taken') or 'sem data')[:10],
        'decision': _decision(row.get('decision'), row.get('reason')),
        'reason': row.get('reason') or '',
    }


def _disk(vault_path: str | None, pending: int = 0) -> dict:
    if not vault_path:
        return {'total': 0, 'used': 0, 'free': 0, 'pending': pending}
    try:
        usage = shutil.disk_usage(vault_path)
        return {'total': usage.total, 'used': usage.used, 'free': usage.free, 'pending': pending}
    except Exception:
        return {'total': 0, 'used': 0, 'free': 0, 'pending': pending}


def state(_payload: dict) -> dict:
    started = time.perf_counter()
    init_db()
    vault = get_latest_vault()
    vault_at = time.perf_counter()
    imports = [_import_row(item) for item in list_imports(80)]
    imports_at = time.perf_counter()
    selected_id = imports[0]['id'] if imports else None
    files = []
    pending = imports[0]['bytesNew'] if imports and imports[0]['status'] in {'ready', 'running'} else 0
    vault_path = str(vault['root_path']) if vault else ''
    insights = _import_insights(selected_id)
    insights_at = time.perf_counter()
    gallery_data = _gallery_payload(GALLERY_ITEM_LIMIT)
    gallery_at = time.perf_counter()
    progress_data = _progress_payload()
    progress_at = time.perf_counter()
    return {
        'vault': {
            'id': vault['id'] if vault else None,
            'name': vault['label'] if vault else 'Galeria PhotoVault',
            'path': vault_path,
            'pattern': vault['pattern'] if vault else '{year}/{month:02d}',
        },
        'imports': imports,
        'files': files,
        'importInsights': insights,
        'gallery': gallery_data,
        'disk': _disk(vault_path, pending),
        'progress': progress_data,
        'logPath': str(get_log_path()),
        'timings': {
            'vaultSeconds': vault_at - started,
            'importsSeconds': imports_at - vault_at,
            'insightsSeconds': insights_at - imports_at,
            'gallerySeconds': gallery_at - insights_at,
            'progressSeconds': progress_at - gallery_at,
            'totalSeconds': time.perf_counter() - started,
        },
    }


def set_vault(payload: dict) -> dict:
    init_db()
    path = payload.get('path')
    name = (payload.get('name') or 'Galeria PhotoVault').strip()
    pattern = payload.get('pattern') or '{year}/{month:02d}'
    if not name:
        raise ValueError('Nome da galeria obrigatorio')
    if not path:
        raise ValueError('Vault path obrigatório')
    if not validate_pattern(pattern):
        raise ValueError('Padrao de organizacao invalido')
    Path(path).mkdir(parents=True, exist_ok=True)
    vault_id = save_vault(name, path, pattern)
    return {'ok': True, 'vault': {'id': vault_id, 'name': name, 'path': path, 'pattern': pattern}}


def analyze_import(payload: dict) -> dict:
    init_db()
    source = payload.get('sourcePath')
    vault_path = payload.get('vaultPath')
    if not source:
        raise ValueError('sourcePath obrigatório')
    if not vault_path:
        latest = get_latest_vault()
        vault_path = latest['root_path'] if latest else None
    if not vault_path:
        raise ValueError('Configure o vault antes de importar')
    validate_import_paths(Path(source), Path(vault_path))
    log.info("bridge analyze_import start source=%s vault=%s", source, vault_path)
    _write_progress('analysis', f'Iniciando analise de {source}', path=source)

    def on_progress(path: Path, done: int) -> None:
        if done == 1 or done % 5 == 0:
            _write_progress(
                'analysis',
                f'Analisando {done} arquivos...',
                current=done,
                path=str(path),
            )

    analysis = create_import_analysis(
        source_path=Path(source),
        vault_root=Path(vault_path),
        pattern=payload.get('pattern') or '{year}/{month:02d}',
        mode=payload.get('mode') or 'copy',
        name=payload.get('name') or Path(source).name,
        callback=on_progress,
    )
    _write_progress(
        'analysis',
        f'Analise concluida: {analysis.files_found} encontrados, {analysis.files_new} novos, {analysis.files_duplicate} duplicados.',
        current=analysis.files_found,
        total=analysis.files_found,
        path=str(source),
        status='done',
    )
    log.info(
        "bridge analyze_import done import_id=%s found=%s new=%s duplicate=%s errors=%s",
        analysis.import_id,
        analysis.files_found,
        analysis.files_new,
        analysis.files_duplicate,
        analysis.errors,
    )
    return {'ok': True, 'importId': analysis.import_id, **state({})}


def files(payload: dict) -> dict:
    init_db()
    import_id = int(payload.get('importId'))
    limit = int(payload.get('limit') or GALLERY_ITEM_LIMIT)
    return {'files': [_file_row(item) for item in get_import_files(import_id, limit=limit)]}


def gallery(payload: dict) -> dict:
    init_db()
    limit = int(payload.get('limit') or GALLERY_ITEM_LIMIT)
    ensure = bool(payload.get('ensureThumbnails'))
    assets = list_gallery_assets(limit)
    items = [_gallery_row(item, include_thumb=not ensure) for item in assets]
    if ensure:
        hydrated = []
        for row in assets:
            path = Path(row.get('path') or '')
            ensure_thumbnail(path) if path.exists() else None
            hydrated.append(_gallery_row(row))
        items = hydrated
    payload = _gallery_payload(limit)
    payload['items'] = items
    return payload


def enrich_metadata(payload: dict) -> dict:
    init_db()
    limit = int(payload.get('limit') or 1000)
    log.info("bridge enrich_metadata start limit=%s", limit)
    _write_progress('metadata', 'Enriquecendo metadados da galeria...', total=limit)

    def on_progress(current: int, total: int, path: Path) -> None:
        if current == 1 or current == total or current % 5 == 0:
            _write_progress(
                'metadata',
                f'ExifTool processando {current} de {total}...',
                current=current,
                total=total,
                path=str(path),
            )

    result = enrich_gallery_metadata(limit=limit, callback=on_progress)
    status = 'warning' if result.unavailable else 'done'
    message = (
        'ExifTool nao encontrado. Instale o ExifTool e tente novamente.'
        if result.unavailable
        else f'Metadados enriquecidos: {result.enriched} atualizados, {result.skipped} ignorados, {result.errors} erros.'
    )
    _write_progress(
        'metadata',
        message,
        current=result.total,
        total=result.total,
        status=status,
        metrics=result.as_dict(),
    )
    log.info("bridge enrich_metadata done result=%s", result.as_dict())
    return {'ok': not result.unavailable, 'result': result.as_dict(), **state({})}


def import_insights(payload: dict) -> dict:
    init_db()
    return _import_insights(int(payload.get('importId')))


def update_decisions(payload: dict) -> dict:
    init_db()
    decision = payload.get('decision')
    ids = payload.get('ids') or []
    if decision not in {'import', 'skip', 'review'}:
        raise ValueError('Decisão inválida')
    for file_id in ids:
        update_import_file_decision(int(file_id), decision)
    return {'ok': True, 'importInsights': _import_insights(int(payload.get('importId'))) if payload.get('importId') else None}


def update_decision_group(payload: dict) -> dict:
    init_db()
    import_id = int(payload.get('importId'))
    reason = payload.get('reason')
    decision = payload.get('decision')
    if decision not in {'import', 'skip', 'review'}:
        raise ValueError('Decisão inválida')
    files = get_import_files(import_id, limit=100000, reason=reason)
    for item in files:
        update_import_file_decision(int(item['id']), decision)
    return {'ok': True, 'updated': len(files), 'importInsights': _import_insights(import_id)}


def execute_import(payload: dict) -> dict:
    init_db()
    plan_id = payload.get('planId')
    if not plan_id:
        raise ValueError('planId obrigatório')
    log.info("bridge execute_import start plan_id=%s", plan_id)
    _write_progress('execution', f'Executando plano {plan_id}...', path=str(plan_id))

    execution_started = time.perf_counter()
    last_file_mbps = 0.0
    last_file_seconds = 0.0

    def on_progress(current: int, total: int, src: Path, metrics: dict | None = None) -> None:
        nonlocal last_file_mbps, last_file_seconds
        if current not in {0, total - 1} and current % 10 != 0 and (metrics or {}).get('event') not in {'error'}:
            return
        elapsed = max(time.perf_counter() - execution_started, 0.001)
        done = max(current, 0)
        speed = ((metrics or {}).get('bytes_imported') or 0) / 1024 / 1024 / elapsed
        remaining = max(total - done, 0)
        eta = (elapsed / done * remaining) if done else 0
        last_file = (metrics or {}).get('last_file') or {}
        if last_file.get('mbps'):
            last_file_mbps = float(last_file.get('mbps') or 0)
            last_file_seconds = float(last_file.get('total_seconds') or 0)
        progress_metrics = {
            'elapsedSeconds': elapsed,
            'etaSeconds': eta,
            'throughputMbps': speed,
            'bytesImported': (metrics or {}).get('bytes_imported') or 0,
            'filesCopied': (metrics or {}).get('processed') or 0,
            'filesSkipped': (metrics or {}).get('skipped') or 0,
            'filesErrored': (metrics or {}).get('errors') or 0,
            'lastFileMbps': last_file_mbps,
            'lastFileSeconds': last_file_seconds,
            'dbSeconds': (metrics or {}).get('db_seconds') or 0,
            'finalizeSeconds': (metrics or {}).get('finalize_seconds') or 0,
        }
        _write_progress(
            'execution',
            f'Copiando {done} de {total} | {format_size(progress_metrics["bytesImported"])} | {speed:.1f} MB/s',
            current=done,
            total=total,
            path=str(src),
            metrics=progress_metrics,
        )

    verify_mode = payload.get('verifyMode') or 'size'
    try:
        result = execute_ingest_plan(int(plan_id), callback=on_progress, verify_mode=verify_mode)
    except Exception as exc:
        _write_progress(
            'execution',
            str(exc),
            status='error',
            metrics={
                'elapsedSeconds': max(time.perf_counter() - execution_started, 0.001),
                'throughputMbps': 0,
                'bytesImported': 0,
                'filesCopied': 0,
                'filesSkipped': 0,
                'filesErrored': 1,
            },
        )
        raise
    final_status = 'done' if result.get('errors', 0) == 0 else 'error'
    _write_progress(
        'execution',
        f'Execucao concluida: {result.get("processed", 0)} copiados, {result.get("skipped", 0)} ignorados, {result.get("errors", 0)} erros em {result.get("total_seconds", 0):.1f}s ({result.get("throughput_mbps", 0):.1f} MB/s).',
        current=result.get('total', 0),
        total=result.get('total', 0),
        status=final_status,
        metrics={
            'elapsedSeconds': result.get('total_seconds', 0),
            'throughputMbps': result.get('throughput_mbps', 0),
            'bytesImported': result.get('bytes_imported', 0),
            'filesCopied': result.get('processed', 0),
            'filesSkipped': result.get('skipped', 0),
            'filesErrored': result.get('errors', 0),
            'dbSeconds': result.get('db_seconds', 0),
            'finalizeSeconds': result.get('finalize_seconds', 0),
            'copySeconds': result.get('copy_seconds', 0),
            'verifySeconds': result.get('verify_seconds', 0),
            'largestFile': result.get('largest_file'),
            'slowestFile': result.get('slowest_file'),
        },
    )
    log.info("bridge execute_import done plan_id=%s result=%s", plan_id, result)
    return {'ok': True, 'result': result}


def reset_all(_payload: dict) -> dict:
    if not _payload.get('confirmReset'):
        raise ValueError('Confirmacao obrigatoria para resetar o ambiente')
    root = validate_reset_root(CONFIG_DIR)
    if root.exists():
        for child in root.iterdir():
            try:
                if child == get_log_path():
                    continue
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
            except PermissionError:
                log.warning("reset_all skipped locked path=%s", child)
    init_db()
    return {'ok': True, **state({})}


def progress(_payload: dict) -> dict:
    return {'progress': _progress_payload(), 'logPath': str(get_log_path())}


def logs(payload: dict) -> dict:
    return {'logPath': str(get_log_path()), 'lines': _tail_log(int(payload.get('lines') or 120))}


COMMANDS = {
    'state': state,
    'set_vault': set_vault,
    'analyze_import': analyze_import,
    'files': files,
    'import_insights': import_insights,
    'update_decisions': update_decisions,
    'update_decision_group': update_decision_group,
    'execute_import': execute_import,
    'reset_all': reset_all,
    'gallery': gallery,
    'enrich_metadata': enrich_metadata,
    'progress': progress,
    'logs': logs,
}


def main() -> int:
    setup_logging()
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=COMMANDS.keys())
    args = parser.parse_args()
    payload = _read_payload()
    should_log_command = args.command != 'progress'
    try:
        if should_log_command:
            log.info("bridge command start command=%s", args.command)
        _print(COMMANDS[args.command](payload))
        if should_log_command:
            log.info("bridge command done command=%s", args.command)
        return 0
    except Exception as exc:
        log.exception("bridge command failed command=%s", args.command)
        _write_progress(args.command, str(exc), status='error')
        _print({'ok': False, 'error': str(exc)})
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
