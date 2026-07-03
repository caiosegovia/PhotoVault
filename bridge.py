import argparse
import json
import logging
import shutil
import sys
import time
from pathlib import Path

from core.database import (
    get_import_files,
    get_latest_vault,
    init_db,
    list_imports,
    save_vault,
    update_import_file_decision,
)
from core.imports import create_import_analysis
from core.ingestion import execute_ingest_plan
from utils.constants import CONFIG_DIR
from utils.formatting import format_size
from utils.logging import get_log_path, setup_logging


PROGRESS_PATH = CONFIG_DIR / "progress.json"
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
                    path: str = "", status: str = "running") -> None:
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
    PROGRESS_PATH.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')


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
    init_db()
    vault = get_latest_vault()
    imports = [_import_row(item) for item in list_imports(80)]
    selected_id = imports[0]['id'] if imports else None
    files = [_file_row(item) for item in get_import_files(selected_id, limit=300)] if selected_id else []
    pending = imports[0]['bytesNew'] if imports else 0
    vault_path = str(vault['root_path']) if vault else ''
    return {
        'vault': {
            'id': vault['id'] if vault else None,
            'path': vault_path,
            'pattern': vault['pattern'] if vault else '{year}/{month:02d}',
        },
        'imports': imports,
        'files': files,
        'disk': _disk(vault_path, pending),
        'progress': _progress_payload(),
        'logPath': str(get_log_path()),
    }


def set_vault(payload: dict) -> dict:
    init_db()
    path = payload.get('path')
    pattern = payload.get('pattern') or '{year}/{month:02d}'
    if not path:
        raise ValueError('Vault path obrigatório')
    Path(path).mkdir(parents=True, exist_ok=True)
    vault_id = save_vault('Galeria PhotoVault', path, pattern)
    return {'ok': True, 'vault': {'id': vault_id, 'path': path, 'pattern': pattern}}


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
    limit = int(payload.get('limit') or 1000)
    return {'files': [_file_row(item) for item in get_import_files(import_id, limit=limit)]}


def update_decisions(payload: dict) -> dict:
    init_db()
    decision = payload.get('decision')
    ids = payload.get('ids') or []
    if decision not in {'import', 'skip', 'review'}:
        raise ValueError('Decisão inválida')
    for file_id in ids:
        update_import_file_decision(int(file_id), decision)
    return {'ok': True}


def execute_import(payload: dict) -> dict:
    init_db()
    plan_id = payload.get('planId')
    if not plan_id:
        raise ValueError('planId obrigatório')
    log.info("bridge execute_import start plan_id=%s", plan_id)
    _write_progress('execution', f'Executando plano {plan_id}...', path=str(plan_id))

    def on_progress(current: int, total: int, src: Path) -> None:
        _write_progress(
            'execution',
            f'Executando {current + 1} de {total}...',
            current=current + 1,
            total=total,
            path=str(src),
        )

    result = execute_ingest_plan(int(plan_id), callback=on_progress)
    _write_progress(
        'execution',
        f'Execucao concluida: {result.get("processed", 0)} copiados, {result.get("skipped", 0)} ignorados, {result.get("errors", 0)} erros.',
        current=result.get('total', 0),
        total=result.get('total', 0),
        status='done',
    )
    log.info("bridge execute_import done plan_id=%s result=%s", plan_id, result)
    return {'ok': True, 'result': result, **state({})}


def reset_all(_payload: dict) -> dict:
    if CONFIG_DIR.exists():
        for child in CONFIG_DIR.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
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
    'update_decisions': update_decisions,
    'execute_import': execute_import,
    'reset_all': reset_all,
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
