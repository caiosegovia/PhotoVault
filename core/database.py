import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Optional

from utils.constants import DB_PATH


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialize SQLite schema."""
    with _get_conn() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA cache_size=-32000")  # 32 MB
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY,
                path TEXT UNIQUE,
                hash_sha256 TEXT,
                hash_phash TEXT,
                date_taken TIMESTAMP,
                size INTEGER,
                media_type TEXT,
                extension TEXT,
                mtime REAL,
                source_id INTEGER,
                camera_make TEXT,
                camera_model TEXT,
                lens_model TEXT,
                software TEXT,
                device_type TEXT,
                device_name TEXT,
                origin_hint TEXT,
                width INTEGER,
                height INTEGER,
                duration REAL,
                has_exif INTEGER DEFAULT 0,
                scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS sources (
                id INTEGER PRIMARY KEY,
                label TEXT,
                type TEXT,
                role TEXT DEFAULT 'origin',
                root_path TEXT UNIQUE,
                volume_id TEXT,
                last_seen_at TIMESTAMP,
                last_scan_at TIMESTAMP,
                status TEXT DEFAULT 'online'
            );
            CREATE TABLE IF NOT EXISTS scan_jobs (
                id INTEGER PRIMARY KEY,
                source_id INTEGER,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                files_seen INTEGER DEFAULT 0,
                files_added INTEGER DEFAULT 0,
                files_changed INTEGER DEFAULT 0,
                files_missing INTEGER DEFAULT 0,
                status TEXT DEFAULT 'completed'
            );
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                sources TEXT,
                destination TEXT,
                files_processed INTEGER DEFAULT 0,
                files_moved INTEGER DEFAULT 0,
                duplicates_found INTEGER DEFAULT 0,
                space_freed INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS destination_index (
                destination TEXT NOT NULL,
                path        TEXT NOT NULL,
                size        INTEGER,
                mtime       REAL,
                sha256      TEXT,
                PRIMARY KEY (destination, path)
            );
            CREATE TABLE IF NOT EXISTS vaults (
                id INTEGER PRIMARY KEY,
                label TEXT NOT NULL,
                root_path TEXT UNIQUE NOT NULL,
                pattern TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS assets (
                id INTEGER PRIMARY KEY,
                sha256 TEXT UNIQUE NOT NULL,
                size INTEGER NOT NULL,
                media_type TEXT,
                extension TEXT,
                date_taken TIMESTAMP,
                width INTEGER,
                height INTEGER,
                duration REAL,
                best_instance_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS asset_instances (
                id INTEGER PRIMARY KEY,
                asset_id INTEGER NOT NULL,
                file_id INTEGER,
                source_id INTEGER,
                path TEXT NOT NULL,
                role TEXT DEFAULT 'origin',
                quality_score INTEGER DEFAULT 0,
                exists_at_scan INTEGER DEFAULT 1,
                copied_at TIMESTAMP,
                verified_at TIMESTAMP,
                UNIQUE(asset_id, path)
            );
            CREATE TABLE IF NOT EXISTS ingest_plans (
                id INTEGER PRIMARY KEY,
                vault_id INTEGER NOT NULL,
                status TEXT DEFAULT 'planned',
                mode TEXT DEFAULT 'copy',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                summary TEXT
            );
            CREATE TABLE IF NOT EXISTS ingest_operations (
                id INTEGER PRIMARY KEY,
                plan_id INTEGER NOT NULL,
                asset_id INTEGER,
                src_path TEXT NOT NULL,
                dst_path TEXT NOT NULL,
                action TEXT NOT NULL,
                reason TEXT,
                status TEXT DEFAULT 'planned',
                error TEXT,
                sha256 TEXT,
                size INTEGER,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                UNIQUE(plan_id, src_path, dst_path)
            );
            CREATE TABLE IF NOT EXISTS imports (
                id INTEGER PRIMARY KEY,
                vault_id INTEGER NOT NULL,
                ingest_plan_id INTEGER,
                name TEXT NOT NULL,
                source_path TEXT NOT NULL,
                status TEXT DEFAULT 'created',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                analyzed_at TIMESTAMP,
                completed_at TIMESTAMP,
                files_found INTEGER DEFAULT 0,
                files_new INTEGER DEFAULT 0,
                files_duplicate INTEGER DEFAULT 0,
                files_existing INTEGER DEFAULT 0,
                files_review INTEGER DEFAULT 0,
                files_imported INTEGER DEFAULT 0,
                files_skipped INTEGER DEFAULT 0,
                files_error INTEGER DEFAULT 0,
                bytes_found INTEGER DEFAULT 0,
                bytes_new INTEGER DEFAULT 0,
                bytes_imported INTEGER DEFAULT 0,
                summary TEXT
            );
            CREATE TABLE IF NOT EXISTS import_files (
                id INTEGER PRIMARY KEY,
                import_id INTEGER NOT NULL,
                ingest_operation_id INTEGER,
                asset_id INTEGER,
                src_path TEXT NOT NULL,
                dst_path TEXT,
                sha256 TEXT,
                status TEXT DEFAULT 'planned',
                decision TEXT,
                reason TEXT,
                size INTEGER,
                media_type TEXT,
                extension TEXT,
                date_taken TIMESTAMP,
                error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                UNIQUE(import_id, src_path)
            );
            CREATE TABLE IF NOT EXISTS audit_events (
                id INTEGER PRIMARY KEY,
                entity_type TEXT NOT NULL,
                entity_id INTEGER,
                event_type TEXT NOT NULL,
                message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                payload TEXT
            );
            CREATE TABLE IF NOT EXISTS metadata_extractions (
                id INTEGER PRIMARY KEY,
                file_id INTEGER,
                asset_id INTEGER,
                path TEXT NOT NULL,
                extractor TEXT NOT NULL,
                extractor_version TEXT,
                extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                mtime REAL,
                status TEXT DEFAULT 'ok',
                raw_json TEXT,
                UNIQUE(path, extractor)
            );
            CREATE TABLE IF NOT EXISTS asset_processing_state (
                id INTEGER PRIMARY KEY,
                asset_id INTEGER NOT NULL,
                instance_id INTEGER,
                path TEXT NOT NULL,
                processor TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                attempts INTEGER DEFAULT 0,
                last_error TEXT,
                source_mtime REAL,
                source_size INTEGER,
                processor_version TEXT,
                first_requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(asset_id, path, processor)
            );
            CREATE TABLE IF NOT EXISTS catalog_tags (
                id INTEGER PRIMARY KEY,
                label TEXT UNIQUE NOT NULL,
                source TEXT DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS asset_tags (
                asset_id INTEGER NOT NULL,
                tag_id INTEGER NOT NULL,
                confidence REAL,
                source TEXT DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(asset_id, tag_id, source)
            );
            CREATE TABLE IF NOT EXISTS catalog_notes (
                id INTEGER PRIMARY KEY,
                asset_id INTEGER,
                note_type TEXT NOT NULL,
                source TEXT DEFAULT 'user',
                confidence REAL,
                body TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS background_jobs (
                id INTEGER PRIMARY KEY,
                kind TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'queued',
                entity_type TEXT,
                entity_id INTEGER,
                payload TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                error TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_hash ON files(hash_sha256);
            CREATE INDEX IF NOT EXISTS idx_phash ON files(hash_phash);
            CREATE INDEX IF NOT EXISTS idx_path ON files(path);
            CREATE INDEX IF NOT EXISTS idx_dest_hash ON destination_index(destination, sha256);
            CREATE INDEX IF NOT EXISTS idx_dest_size ON destination_index(destination, size);
            CREATE INDEX IF NOT EXISTS idx_assets_sha256 ON assets(sha256);
            CREATE INDEX IF NOT EXISTS idx_asset_instances_asset ON asset_instances(asset_id);
            CREATE INDEX IF NOT EXISTS idx_asset_instances_path ON asset_instances(path);
            CREATE INDEX IF NOT EXISTS idx_ingest_operations_plan ON ingest_operations(plan_id);
            CREATE INDEX IF NOT EXISTS idx_ingest_operations_status ON ingest_operations(status);
            CREATE INDEX IF NOT EXISTS idx_imports_status ON imports(status);
            CREATE INDEX IF NOT EXISTS idx_imports_created ON imports(created_at);
            CREATE INDEX IF NOT EXISTS idx_import_files_import ON import_files(import_id);
            CREATE INDEX IF NOT EXISTS idx_import_files_reason ON import_files(reason);
            CREATE INDEX IF NOT EXISTS idx_metadata_path ON metadata_extractions(path);
            CREATE INDEX IF NOT EXISTS idx_metadata_file ON metadata_extractions(file_id);
            CREATE INDEX IF NOT EXISTS idx_metadata_asset ON metadata_extractions(asset_id);
            CREATE INDEX IF NOT EXISTS idx_processing_processor_status ON asset_processing_state(processor, status);
            CREATE INDEX IF NOT EXISTS idx_processing_asset ON asset_processing_state(asset_id);
            CREATE INDEX IF NOT EXISTS idx_catalog_notes_asset ON catalog_notes(asset_id);
            CREATE INDEX IF NOT EXISTS idx_background_jobs_status ON background_jobs(kind, status);
        """)
        try:
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS catalog_search
                USING fts5(path, name, media_type, extension, camera, lens, device, tags)
            """)
        except sqlite3.OperationalError:
            pass
        # Migrate: add new columns if they don't exist yet
        for col_sql in [
            "ALTER TABLE sessions ADD COLUMN errors INTEGER DEFAULT 0",
            "ALTER TABLE sessions ADD COLUMN total_files INTEGER DEFAULT 0",
            "ALTER TABLE sessions ADD COLUMN status TEXT DEFAULT 'completed'",
            "ALTER TABLE files ADD COLUMN camera_make TEXT",
            "ALTER TABLE files ADD COLUMN source_id INTEGER",
            "ALTER TABLE files ADD COLUMN camera_model TEXT",
            "ALTER TABLE files ADD COLUMN lens_model TEXT",
            "ALTER TABLE files ADD COLUMN software TEXT",
            "ALTER TABLE files ADD COLUMN device_type TEXT",
            "ALTER TABLE files ADD COLUMN device_name TEXT",
            "ALTER TABLE files ADD COLUMN origin_hint TEXT",
            "ALTER TABLE files ADD COLUMN width INTEGER",
            "ALTER TABLE files ADD COLUMN height INTEGER",
            "ALTER TABLE files ADD COLUMN duration REAL",
            "ALTER TABLE files ADD COLUMN has_exif INTEGER DEFAULT 0",
            "ALTER TABLE sources ADD COLUMN role TEXT DEFAULT 'origin'",
            "ALTER TABLE ingest_plans ADD COLUMN import_id INTEGER",
        ]:
            try:
                conn.execute(col_sql)
            except Exception:
                pass
        for idx_sql in [
            "CREATE INDEX IF NOT EXISTS idx_files_device ON files(device_name)",
            "CREATE INDEX IF NOT EXISTS idx_files_device_type ON files(device_type)",
            "CREATE INDEX IF NOT EXISTS idx_files_source ON files(source_id)",
            "CREATE INDEX IF NOT EXISTS idx_sources_role ON sources(role)",
            "CREATE INDEX IF NOT EXISTS idx_assets_sha256 ON assets(sha256)",
            "CREATE INDEX IF NOT EXISTS idx_asset_instances_asset ON asset_instances(asset_id)",
            "CREATE INDEX IF NOT EXISTS idx_asset_instances_path ON asset_instances(path)",
            "CREATE INDEX IF NOT EXISTS idx_ingest_operations_plan ON ingest_operations(plan_id)",
            "CREATE INDEX IF NOT EXISTS idx_ingest_operations_status ON ingest_operations(status)",
            "CREATE INDEX IF NOT EXISTS idx_imports_status ON imports(status)",
            "CREATE INDEX IF NOT EXISTS idx_imports_created ON imports(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_import_files_import ON import_files(import_id)",
            "CREATE INDEX IF NOT EXISTS idx_import_files_reason ON import_files(reason)",
            "CREATE INDEX IF NOT EXISTS idx_metadata_path ON metadata_extractions(path)",
            "CREATE INDEX IF NOT EXISTS idx_metadata_file ON metadata_extractions(file_id)",
            "CREATE INDEX IF NOT EXISTS idx_metadata_asset ON metadata_extractions(asset_id)",
            "CREATE INDEX IF NOT EXISTS idx_processing_processor_status ON asset_processing_state(processor, status)",
            "CREATE INDEX IF NOT EXISTS idx_processing_asset ON asset_processing_state(asset_id)",
            "CREATE INDEX IF NOT EXISTS idx_catalog_notes_asset ON catalog_notes(asset_id)",
            "CREATE INDEX IF NOT EXISTS idx_background_jobs_status ON background_jobs(kind, status)",
        ]:
            try:
                conn.execute(idx_sql)
            except Exception:
                pass


def save_metadata_extraction_conn(conn: sqlite3.Connection, file_id: Optional[int],
                                  asset_id: Optional[int], path: str, extractor: str,
                                  extractor_version: Optional[str], mtime: Optional[float],
                                  status: str, raw: dict) -> None:
    """Persist raw metadata/provenance for later insights and agent queries."""
    conn.execute(
        """INSERT INTO metadata_extractions(file_id, asset_id, path, extractor,
                                            extractor_version, mtime, status, raw_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(path, extractor) DO UPDATE SET
               file_id=COALESCE(excluded.file_id, metadata_extractions.file_id),
               asset_id=COALESCE(excluded.asset_id, metadata_extractions.asset_id),
               extractor_version=excluded.extractor_version,
               mtime=excluded.mtime,
               status=excluded.status,
               raw_json=excluded.raw_json,
               extracted_at=CURRENT_TIMESTAMP""",
        (file_id, asset_id, path, extractor, extractor_version, mtime, status, json.dumps(raw, default=str)),
    )


def refresh_catalog_search_conn(conn: sqlite3.Connection, path: str, media_type: Optional[str],
                                extension: Optional[str], camera: str = '',
                                lens: str = '', device: str = '', tags: str = '') -> None:
    """Refresh the FTS row used by gallery search and future agent access."""
    try:
        conn.execute("DELETE FROM catalog_search WHERE path = ?", (path,))
        conn.execute(
            """INSERT INTO catalog_search(path, name, media_type, extension, camera, lens, device, tags)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (path, Path(path).name, media_type or '', extension or '', camera, lens, device, tags),
        )
    except sqlite3.OperationalError:
        pass


def _path_stats(path: str) -> tuple[Optional[float], Optional[int]]:
    try:
        stat = Path(path).stat()
        return stat.st_mtime, stat.st_size
    except OSError:
        return None, None


def _state_error(raw: dict) -> Optional[str]:
    value = raw.get('error') if isinstance(raw, dict) else None
    return str(value) if value else None


def _ensure_processing_state_conn(conn: sqlite3.Connection, asset_id: int, instance_id: Optional[int],
                                  path: str, processor: str, status: str = 'pending',
                                  source_mtime: Optional[float] = None,
                                  source_size: Optional[int] = None,
                                  processor_version: Optional[str] = None,
                                  last_error: Optional[str] = None) -> None:
    conn.execute(
        """INSERT INTO asset_processing_state(
               asset_id, instance_id, path, processor, status, source_mtime,
               source_size, processor_version, last_error
           )
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(asset_id, path, processor) DO UPDATE SET
               instance_id=COALESCE(excluded.instance_id, asset_processing_state.instance_id),
               path=excluded.path,
               source_mtime=COALESCE(excluded.source_mtime, asset_processing_state.source_mtime),
               source_size=COALESCE(excluded.source_size, asset_processing_state.source_size),
               updated_at=CURRENT_TIMESTAMP""",
        (asset_id, instance_id, path, processor, status, source_mtime, source_size, processor_version, last_error),
    )


def _finish_processing_state_conn(conn: sqlite3.Connection, asset_id: int, path: str, processor: str,
                                  status: str, processor_version: Optional[str],
                                  source_mtime: Optional[float], source_size: Optional[int],
                                  last_error: Optional[str] = None) -> None:
    row = conn.execute(
        "SELECT id, instance_id FROM asset_processing_state WHERE asset_id=? AND path=? AND processor=?",
        (asset_id, path, processor),
    ).fetchone()
    instance = conn.execute(
        "SELECT id FROM asset_instances WHERE asset_id=? AND path=?",
        (asset_id, path),
    ).fetchone()
    instance_id = instance['id'] if instance else (row['instance_id'] if row else None)
    _ensure_processing_state_conn(
        conn,
        asset_id=asset_id,
        instance_id=instance_id,
        path=path,
        processor=processor,
        status=status,
        source_mtime=source_mtime,
        source_size=source_size,
        processor_version=processor_version,
        last_error=last_error,
    )
    conn.execute(
        """UPDATE asset_processing_state
           SET status=?,
               processor_version=?,
               source_mtime=?,
               source_size=?,
               last_error=?,
               completed_at=CURRENT_TIMESTAMP,
               updated_at=CURRENT_TIMESTAMP
           WHERE asset_id=? AND path=? AND processor=?""",
        (status, processor_version, source_mtime, source_size, last_error, asset_id, path, processor),
    )


def ensure_processing_coverage(processor: str = 'exiftool') -> dict:
    """Ensure every destination asset has an explicit processing state."""
    with _get_conn() as conn:
        conn.execute(
            """UPDATE asset_processing_state
               SET status='pending', updated_at=CURRENT_TIMESTAMP
               WHERE processor=? AND status='running'""",
            (processor,),
        )
        metadata = conn.execute(
            """SELECT me.asset_id, me.path, me.extractor_version, me.mtime, me.status, me.raw_json,
                      ai.id AS instance_id, a.size AS source_size
               FROM metadata_extractions me
               LEFT JOIN asset_instances ai ON ai.asset_id = me.asset_id AND ai.path = me.path
               LEFT JOIN assets a ON a.id = me.asset_id
               WHERE me.extractor=? AND me.asset_id IS NOT NULL""",
            (processor,),
        ).fetchall()
        for row in metadata:
            status = row['status'] if row['status'] in {'ok', 'error', 'missing'} else 'error'
            raw = json.loads(row['raw_json'] or '{}') if row['raw_json'] else {}
            _ensure_processing_state_conn(
                conn,
                asset_id=int(row['asset_id']),
                instance_id=row['instance_id'],
                path=row['path'],
                processor=processor,
                status=status,
                source_mtime=row['mtime'],
                source_size=row['source_size'],
                processor_version=row['extractor_version'],
                last_error=_state_error(raw),
            )
            conn.execute(
                """UPDATE asset_processing_state
                   SET status=?, processor_version=?, source_mtime=?, source_size=?,
                       last_error=?, completed_at=COALESCE(completed_at, CURRENT_TIMESTAMP),
                       updated_at=CURRENT_TIMESTAMP
                   WHERE asset_id=? AND path=? AND processor=?""",
                (
                    status,
                    row['extractor_version'],
                    row['mtime'],
                    row['source_size'],
                    _state_error(raw),
                    row['asset_id'],
                    row['path'],
                    processor,
                ),
            )

        destinations = conn.execute(
            """SELECT ai.id AS instance_id, ai.asset_id, ai.path
               FROM asset_instances ai
               WHERE ai.role='destination'""",
        ).fetchall()
        for row in destinations:
            mtime, size = _path_stats(row['path'])
            _ensure_processing_state_conn(
                conn,
                asset_id=int(row['asset_id']),
                instance_id=row['instance_id'],
                path=row['path'],
                processor=processor,
                source_mtime=mtime,
                source_size=size,
            )

        current = conn.execute(
            """SELECT id, path, source_mtime, source_size
               FROM asset_processing_state
               WHERE processor=? AND status='ok'""",
            (processor,),
        ).fetchall()
        for row in current:
            mtime, size = _path_stats(row['path'])
            if mtime is None:
                continue
            stored_mtime = row['source_mtime']
            stored_size = row['source_size']
            changed = (
                stored_mtime is not None
                and (abs(float(stored_mtime) - float(mtime)) > 0.001 or (stored_size is not None and int(stored_size) != int(size or 0)))
            )
            if changed:
                conn.execute(
                    """UPDATE asset_processing_state
                       SET status='stale', source_mtime=?, source_size=?, updated_at=CURRENT_TIMESTAMP
                       WHERE id=?""",
                    (mtime, size, row['id']),
                )
    return processing_summary(processor)


def processing_summary(processor: str = 'exiftool') -> dict:
    try:
        with _get_conn() as conn:
            rows = conn.execute(
                "SELECT status, COUNT(*) AS count FROM asset_processing_state WHERE processor=? GROUP BY status",
                (processor,),
            ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    counts = {row['status']: row['count'] for row in rows}
    total = sum(counts.values())
    return {
        'processor': processor,
        'total': total,
        'pending': counts.get('pending', 0),
        'running': counts.get('running', 0),
        'ok': counts.get('ok', 0),
        'error': counts.get('error', 0),
        'missing': counts.get('missing', 0),
        'stale': counts.get('stale', 0),
    }


def mark_processing_started(state_id: Optional[int]) -> None:
    if not state_id:
        return
    with _get_conn() as conn:
        conn.execute(
            """UPDATE asset_processing_state
               SET status='running',
                   attempts=COALESCE(attempts, 0) + 1,
                   last_error=NULL,
                   started_at=CURRENT_TIMESTAMP,
                   updated_at=CURRENT_TIMESTAMP
               WHERE id=?""",
            (state_id,),
        )


def save_asset_metadata(asset_id: int, path: str, extractor: str, raw: dict,
                        extractor_version: str = '1', mtime: Optional[float] = None,
                        file_id: Optional[int] = None, status: str = 'ok') -> None:
    """Persist metadata directly for an asset produced by the ingest pipeline."""
    with _get_conn() as conn:
        save_metadata_extraction_conn(
            conn,
            file_id=file_id,
            asset_id=asset_id,
            path=path,
            extractor=extractor,
            extractor_version=extractor_version,
            mtime=mtime,
            status=status,
            raw=raw,
        )
        refresh_catalog_search_conn(
            conn,
            path=path,
            media_type=raw.get('media_type') or raw.get('type'),
            extension=raw.get('extension'),
            camera=' '.join(value for value in [raw.get('camera_make'), raw.get('camera_model')] if value),
            lens=raw.get('lens_model') or '',
            device=raw.get('device_name') or raw.get('device_type') or '',
        )


def list_destination_assets_for_enrichment(limit: int = 1000) -> list[dict]:
    """Return destination assets that still need ExifTool processing."""
    ensure_processing_coverage('exiftool')
    with _get_conn() as conn:
        rows = conn.execute(
            """SELECT
                   ai.path AS path,
                   ai.file_id AS file_id,
                   ps.id AS processing_state_id,
                   ps.status AS processing_status,
                   ps.attempts AS processing_attempts,
                   a.id AS asset_id,
                   a.media_type AS media_type,
                   a.extension AS extension,
                   a.date_taken AS date_taken,
                   a.width AS width,
                   a.height AS height,
                   a.duration AS duration
               FROM asset_processing_state ps
               JOIN asset_instances ai
                    ON ai.asset_id = ps.asset_id
                   AND ai.path = ps.path
               JOIN assets a ON a.id = ai.asset_id
               WHERE ai.role = 'destination'
                 AND ps.processor = 'exiftool'
                 AND ps.status IN ('pending', 'error', 'stale')
               ORDER BY
                   CASE ps.status WHEN 'pending' THEN 0 WHEN 'stale' THEN 1 ELSE 2 END,
                   ps.updated_at,
                   ai.id DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def _metadata_date(value: object) -> Optional[str]:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, 'isoformat') else str(value)


def apply_asset_metadata_enrichment(asset_id: int, path: str, extractor: str,
                                    extractor_version: Optional[str], status: str,
                                    raw: dict, normalized: dict,
                                    mtime: Optional[float] = None,
                                    file_id: Optional[int] = None) -> None:
    """Persist rich metadata and promote normalized fields to the catalog."""
    date_taken = _metadata_date(normalized.get('date_taken'))
    media_type = normalized.get('media_type')
    extension = normalized.get('extension')
    width = normalized.get('width')
    height = normalized.get('height')
    duration = normalized.get('duration')
    camera_make = normalized.get('camera_make')
    camera_model = normalized.get('camera_model')
    lens_model = normalized.get('lens_model')
    software = normalized.get('software')
    device_type = normalized.get('device_type')
    device_name = normalized.get('device_name')
    origin_hint = normalized.get('origin_hint')
    has_exif = 1 if normalized.get('has_exif') else 0

    with _get_conn() as conn:
        instance = conn.execute(
            "SELECT file_id FROM asset_instances WHERE asset_id=? AND path=?",
            (asset_id, path),
        ).fetchone()
        resolved_file_id = file_id if file_id is not None else (instance['file_id'] if instance else None)
        source_mtime, source_size = _path_stats(path)
        if mtime is not None:
            source_mtime = mtime
        save_metadata_extraction_conn(
            conn,
            file_id=resolved_file_id,
            asset_id=asset_id,
            path=path,
            extractor=extractor,
            extractor_version=extractor_version,
            mtime=mtime,
            status=status,
            raw=raw,
        )
        _finish_processing_state_conn(
            conn,
            asset_id=asset_id,
            path=path,
            processor=extractor,
            status=status,
            processor_version=extractor_version,
            source_mtime=source_mtime,
            source_size=source_size,
            last_error=_state_error(raw),
        )
        if status == 'ok':
            conn.execute(
                """UPDATE assets
                   SET media_type=COALESCE(?, media_type),
                       extension=COALESCE(?, extension),
                       date_taken=COALESCE(?, date_taken),
                       width=COALESCE(?, width),
                       height=COALESCE(?, height),
                       duration=COALESCE(?, duration),
                       updated_at=CURRENT_TIMESTAMP
                   WHERE id=?""",
                (media_type, extension, date_taken, width, height, duration, asset_id),
            )
            if resolved_file_id:
                conn.execute(
                    """UPDATE files
                       SET date_taken=COALESCE(?, date_taken),
                           media_type=COALESCE(?, media_type),
                           extension=COALESCE(?, extension),
                           camera_make=COALESCE(?, camera_make),
                           camera_model=COALESCE(?, camera_model),
                           lens_model=COALESCE(?, lens_model),
                           software=COALESCE(?, software),
                           device_type=COALESCE(?, device_type),
                           device_name=COALESCE(?, device_name),
                           origin_hint=COALESCE(?, origin_hint),
                           width=COALESCE(?, width),
                           height=COALESCE(?, height),
                           duration=COALESCE(?, duration),
                           has_exif=MAX(has_exif, ?)
                       WHERE id=?""",
                    (
                        date_taken, media_type, extension, camera_make, camera_model,
                        lens_model, software, device_type, device_name, origin_hint,
                        width, height, duration, has_exif, resolved_file_id,
                    ),
                )
            refresh_catalog_search_conn(
                conn,
                path=path,
                media_type=media_type,
                extension=extension,
                camera=' '.join(value for value in [camera_make, camera_model] if value),
                lens=lens_model or '',
                device=device_name or device_type or '',
            )


def backfill_catalog_metadata_from_gallery(limit: int = 2000) -> int:
    """Create lightweight metadata rows for existing destination assets."""
    from core.device_detector import classify_device

    with _get_conn() as conn:
        rows = conn.execute(
            """SELECT
                   ai.path AS path,
                   a.id AS asset_id,
                   a.sha256 AS sha256,
                   a.size AS size,
                   a.media_type AS media_type,
                   a.extension AS extension,
                   a.date_taken AS date_taken,
                   a.width AS width,
                   a.height AS height,
                   a.duration AS duration
               FROM asset_instances ai
               JOIN assets a ON a.id = ai.asset_id
               WHERE ai.role = 'destination'
                 AND NOT EXISTS (
                    SELECT 1 FROM metadata_extractions me
                    WHERE me.asset_id = a.id
                 )
               ORDER BY ai.id DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        for row in rows:
            device = classify_device(path=Path(row['path']))
            raw = {
                'sha256': row['sha256'],
                'size': row['size'],
                'media_type': row['media_type'],
                'extension': row['extension'],
                'date_taken': row['date_taken'],
                'width': row['width'],
                'height': row['height'],
                'duration': row['duration'],
                'device_name': device.normalized_name,
                'device_type': device.device_type,
                'origin_hint': device.origin_hint,
            }
            save_metadata_extraction_conn(
                conn,
                file_id=None,
                asset_id=int(row['asset_id']),
                path=row['path'],
                extractor='photovault-backfill',
                extractor_version='1',
                mtime=None,
                status='ok',
                raw=raw,
            )
            refresh_catalog_search_conn(
                conn,
                path=row['path'],
                media_type=row['media_type'],
                extension=row['extension'],
                device=device.normalized_name,
            )
        return len(rows)


def save_file_record(path: str, hash_sha256: Optional[str], hash_phash: Optional[str],
                     date_taken: Optional[datetime], size: int, media_type: str,
                     extension: str, mtime: float, camera_make: Optional[str] = None,
                     camera_model: Optional[str] = None, lens_model: Optional[str] = None,
                     software: Optional[str] = None, device_type: Optional[str] = None,
                     device_name: Optional[str] = None, origin_hint: Optional[str] = None,
                     width: Optional[int] = None, height: Optional[int] = None,
                     duration: Optional[float] = None, has_exif: bool = False,
                     source_id: Optional[int] = None) -> None:
    """Insert or update file record."""
    date_str = date_taken.isoformat() if date_taken else None
    with _get_conn() as conn:
        conn.execute("""
            INSERT INTO files (path, hash_sha256, hash_phash, date_taken, size,
                               media_type, extension, mtime, source_id, camera_make, camera_model,
                               lens_model, software, device_type, device_name,
                               origin_hint, width, height, duration, has_exif, scanned_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(path) DO UPDATE SET
                hash_sha256=excluded.hash_sha256,
                hash_phash=excluded.hash_phash,
                date_taken=excluded.date_taken,
                size=excluded.size,
                media_type=excluded.media_type,
                extension=excluded.extension,
                mtime=excluded.mtime,
                source_id=excluded.source_id,
                camera_make=excluded.camera_make,
                camera_model=excluded.camera_model,
                lens_model=excluded.lens_model,
                software=excluded.software,
                device_type=excluded.device_type,
                device_name=excluded.device_name,
                origin_hint=excluded.origin_hint,
                width=excluded.width,
                height=excluded.height,
                duration=excluded.duration,
                has_exif=excluded.has_exif,
                scanned_at=CURRENT_TIMESTAMP
        """, (path, hash_sha256, hash_phash, date_str, size, media_type, extension, mtime, source_id,
              camera_make, camera_model, lens_model, software, device_type,
              device_name, origin_hint, width, height, duration, 1 if has_exif else 0))
        row = conn.execute("SELECT id FROM files WHERE path = ?", (path,)).fetchone()
        if row:
            payload = {
                'date_taken': date_str,
                'size': size,
                'media_type': media_type,
                'extension': extension,
                'camera_make': camera_make,
                'camera_model': camera_model,
                'lens_model': lens_model,
                'software': software,
                'device_type': device_type,
                'device_name': device_name,
                'origin_hint': origin_hint,
                'width': width,
                'height': height,
                'duration': duration,
                'has_exif': bool(has_exif),
                'hash_sha256': hash_sha256,
            }
            save_metadata_extraction_conn(
                conn,
                file_id=int(row['id']),
                asset_id=None,
                path=path,
                extractor='photovault-core',
                extractor_version='1',
                mtime=mtime,
                status='ok',
                raw=payload,
            )
            refresh_catalog_search_conn(
                conn,
                path=path,
                media_type=media_type,
                extension=extension,
                camera=' '.join(value for value in [camera_make, camera_model] if value),
                lens=lens_model or '',
                device=device_name or device_type or '',
            )


def get_file_by_hash(hash_sha256: str) -> Optional[sqlite3.Row]:
    """Lookup file by exact SHA-256 hash."""
    with _get_conn() as conn:
        return conn.execute(
            "SELECT * FROM files WHERE hash_sha256 = ?", (hash_sha256,)
        ).fetchone()


def get_cached_metadata(path: str, mtime: float) -> Optional[sqlite3.Row]:
    """Get cached metadata if path and mtime match."""
    with _get_conn() as conn:
        return conn.execute(
            "SELECT * FROM files WHERE path = ? AND mtime = ?", (path, mtime)
        ).fetchone()


def save_session(session_data: dict) -> int:
    """Save scan session, return session id."""
    with _get_conn() as conn:
        cur = conn.execute("""
            INSERT INTO sessions (started_at, completed_at, sources, destination,
                                  files_processed, files_moved, duplicates_found, space_freed,
                                  errors, total_files, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_data.get('started_at'),
            session_data.get('completed_at'),
            json.dumps(session_data.get('sources', [])),
            session_data.get('destination'),
            session_data.get('files_processed', 0),
            session_data.get('files_moved', 0),
            session_data.get('duplicates_found', 0),
            session_data.get('space_freed', 0),
            session_data.get('errors', 0),
            session_data.get('total_files', 0),
            session_data.get('status', 'completed'),
        ))
        return cur.lastrowid


def get_scan_history(limit: int = 10) -> list[sqlite3.Row]:
    """Return recent scan sessions."""
    with _get_conn() as conn:
        return conn.execute(
            "SELECT * FROM sessions ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()


def get_all_file_records() -> list[sqlite3.Row]:
    """Return all file records."""
    with _get_conn() as conn:
        return conn.execute("SELECT * FROM files ORDER BY date_taken").fetchall()


def query_gallery_records(filters: Optional[dict] = None, limit: int = 120, offset: int = 0) -> list[sqlite3.Row]:
    """Return paginated file records for the gallery."""
    filters = filters or {}
    where = ["1=1"]
    params: list = []

    media_type = filters.get("media_type")
    if media_type:
        where.append("f.media_type = ?")
        params.append(media_type)

    device_type = filters.get("device_type")
    if device_type:
        where.append("COALESCE(f.device_type, 'unknown') = ?")
        params.append(device_type)

    source_role = filters.get("source_role")
    if source_role:
        where.append("COALESCE(s.role, 'origin') = ?")
        params.append(source_role)

    quality = filters.get("quality")
    if quality == "missing_exif":
        where.append("COALESCE(f.has_exif, 0) = 0")
    elif quality == "large":
        where.append("COALESCE(f.size, 0) >= ?")
        params.append(50 * 1024 * 1024)
    elif quality == "low_resolution":
        where.append("f.width IS NOT NULL AND f.height IS NOT NULL AND (f.width * f.height) < ?")
        params.append(1_000_000)
    elif quality == "high_resolution":
        where.append("f.width IS NOT NULL AND f.height IS NOT NULL AND (f.width * f.height) >= ?")
        params.append(12_000_000)
    elif quality == "needs_review":
        where.append(
            """(
                COALESCE(f.has_exif, 0) = 0
                OR COALESCE(f.size, 0) >= ?
                OR (f.width IS NOT NULL AND f.height IS NOT NULL AND (f.width * f.height) < ?)
                OR f.width IS NULL
                OR f.height IS NULL
            )"""
        )
        params.extend([50 * 1024 * 1024, 1_000_000])

    date_group = filters.get("date_group")
    if date_group == "no_date":
        where.append("f.date_taken IS NULL")
    elif date_group == "recent":
        where.append("f.date_taken >= date('now', '-2 years')")
    elif date_group == "older":
        where.append("f.date_taken < date('now', '-10 years')")
    elif date_group and str(date_group).isdigit():
        where.append("strftime('%Y', f.date_taken) = ?")
        params.append(str(date_group))

    sql = f"""
        SELECT f.*,
               COALESCE(s.label, '') AS source_label,
               COALESCE(s.role, 'origin') AS source_role,
               COALESCE(s.type, '') AS source_type,
               s.root_path AS source_root_path
        FROM files f
        LEFT JOIN sources s ON s.id = f.source_id
        WHERE {' AND '.join(where)}
        ORDER BY
            CASE
                WHEN COALESCE(f.has_exif, 0) = 0 THEN 0
                WHEN COALESCE(f.size, 0) >= {50 * 1024 * 1024} THEN 1
                WHEN f.date_taken IS NULL THEN 2
                ELSE 3
            END,
            f.date_taken DESC,
            f.size DESC
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])
    with _get_conn() as conn:
        return conn.execute(sql, params).fetchall()


def get_all_sources() -> list[dict]:
    """Return all inventory sources."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT id, label, type, role, root_path, status, last_seen_at, last_scan_at FROM sources ORDER BY role, label"
        ).fetchall()
    return [dict(row) for row in rows]


def clear_file_records() -> None:
    """Remove all file records (for fresh scan)."""
    with _get_conn() as conn:
        conn.execute("DELETE FROM files")


def save_source(label: str, source_type: str, root_path: str,
                volume_id: Optional[str] = None, status: str = 'online',
                role: str = 'origin') -> int:
    """Insert or update an inventory source and return its id."""
    now = datetime.now().isoformat()
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO sources(label, type, role, root_path, volume_id, last_seen_at, status)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(root_path) DO UPDATE SET
                   label=excluded.label,
                   type=excluded.type,
                   role=excluded.role,
                   volume_id=excluded.volume_id,
                   last_seen_at=excluded.last_seen_at,
                   status=excluded.status""",
            (label, source_type, role, root_path, volume_id, now, status)
        )
        row = conn.execute("SELECT id FROM sources WHERE root_path=?", (root_path,)).fetchone()
        return int(row['id'])


def start_scan_job(source_id: int) -> int:
    with _get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO scan_jobs(source_id, started_at, status) VALUES (?, ?, ?)",
            (source_id, datetime.now().isoformat(), 'running')
        )
        return cur.lastrowid


def finish_scan_job(job_id: int, files_seen: int, files_added: int,
                    files_changed: int, files_missing: int = 0,
                    status: str = 'completed') -> None:
    with _get_conn() as conn:
        conn.execute(
            """UPDATE scan_jobs
               SET completed_at=?, files_seen=?, files_added=?, files_changed=?,
                   files_missing=?, status=?
               WHERE id=?""",
            (datetime.now().isoformat(), files_seen, files_added,
             files_changed, files_missing, status, job_id)
        )
        conn.execute(
            """UPDATE sources
               SET last_scan_at=?, status=?
               WHERE id=(SELECT source_id FROM scan_jobs WHERE id=?)""",
            (datetime.now().isoformat(), 'online', job_id)
        )


def get_files_by_year() -> dict[int, int]:
    """Return {year: count} for all files with a date_taken."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT strftime('%Y', date_taken) as yr, COUNT(*) as cnt "
            "FROM files WHERE date_taken IS NOT NULL GROUP BY yr ORDER BY yr"
        ).fetchall()
    return {int(row['yr']): row['cnt'] for row in rows if row['yr']}


def get_files_by_device(limit: int = 20) -> list[dict]:
    """Return file counts and bytes grouped by detected device."""
    with _get_conn() as conn:
        rows = conn.execute(
            """SELECT COALESCE(device_name, 'Desconhecido') as device_name,
                      COALESCE(device_type, 'unknown') as device_type,
                      COUNT(*) as cnt,
                      COALESCE(SUM(size), 0) as size_bytes
               FROM files
               GROUP BY device_name, device_type
               ORDER BY cnt DESC
               LIMIT ?""",
            (limit,)
        ).fetchall()
    return [
        {
            'device_name': row['device_name'],
            'device_type': row['device_type'],
            'count': row['cnt'],
            'size_bytes': row['size_bytes'],
        }
        for row in rows
    ]


def get_destination_records(destination: str) -> list[dict]:
    """Return all indexed records for the given destination folder."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT path, size, mtime, sha256 FROM destination_index WHERE destination=?",
            (destination,)
        ).fetchall()
    return [{'path': r[0], 'size': r[1], 'mtime': r[2], 'sha256': r[3]} for r in rows]


def bulk_save_destination_records(destination: str, records: list[dict]) -> None:
    """Insert or update destination index records in batch."""
    with _get_conn() as conn:
        conn.executemany(
            """INSERT OR REPLACE INTO destination_index(destination, path, size, mtime, sha256)
               VALUES (?, ?, ?, ?, ?)""",
            [(destination, r['path'], r['size'], r['mtime'], r['sha256']) for r in records]
        )


def remove_destination_records(destination: str, paths: list[str]) -> None:
    """Remove stale entries (deleted/moved files) from the destination index."""
    with _get_conn() as conn:
        conn.executemany(
            "DELETE FROM destination_index WHERE destination=? AND path=?",
            [(destination, p) for p in paths]
        )


def save_vault(label: str, root_path: str, pattern: str) -> int:
    """Insert or update a vault definition and return its id."""
    now = datetime.now().isoformat()
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO vaults(label, root_path, pattern, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(root_path) DO UPDATE SET
                   label=excluded.label,
                   pattern=excluded.pattern,
                   updated_at=excluded.updated_at""",
            (label, root_path, pattern, now, now)
        )
        row = conn.execute("SELECT id FROM vaults WHERE root_path=?", (root_path,)).fetchone()
        return int(row['id'])


def get_vault(vault_id: int) -> Optional[sqlite3.Row]:
    """Return a vault row by id."""
    with _get_conn() as conn:
        return conn.execute("SELECT * FROM vaults WHERE id=?", (vault_id,)).fetchone()


def get_latest_vault() -> Optional[sqlite3.Row]:
    """Return the most recently updated vault."""
    with _get_conn() as conn:
        return conn.execute(
            "SELECT * FROM vaults ORDER BY updated_at DESC, id DESC LIMIT 1"
        ).fetchone()


def upsert_asset(asset: dict) -> int:
    """Insert or update a logical media asset and return its id."""
    date_taken = asset.get('date_taken')
    date_str = date_taken.isoformat() if hasattr(date_taken, 'isoformat') else date_taken
    now = datetime.now().isoformat()
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO assets(sha256, size, media_type, extension, date_taken,
                                  width, height, duration, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(sha256) DO UPDATE SET
                   size=excluded.size,
                   media_type=COALESCE(excluded.media_type, assets.media_type),
                   extension=COALESCE(excluded.extension, assets.extension),
                   date_taken=COALESCE(excluded.date_taken, assets.date_taken),
                   width=COALESCE(excluded.width, assets.width),
                   height=COALESCE(excluded.height, assets.height),
                   duration=COALESCE(excluded.duration, assets.duration),
                   updated_at=excluded.updated_at""",
            (
                asset['sha256'],
                asset['size'],
                asset.get('media_type'),
                asset.get('extension'),
                date_str,
                asset.get('width'),
                asset.get('height'),
                asset.get('duration'),
                now,
                now,
            )
        )
        row = conn.execute("SELECT id FROM assets WHERE sha256=?", (asset['sha256'],)).fetchone()
        return int(row['id'])


def get_asset_by_sha256(sha256: str) -> Optional[sqlite3.Row]:
    """Lookup a logical asset by SHA-256."""
    with _get_conn() as conn:
        return conn.execute("SELECT * FROM assets WHERE sha256=?", (sha256,)).fetchone()


def save_asset_instance(asset_id: int, path: str, role: str = 'origin',
                        file_id: Optional[int] = None, source_id: Optional[int] = None,
                        quality_score: int = 0, exists_at_scan: bool = True) -> int:
    """Insert or update a physical occurrence of an asset."""
    with _get_conn() as conn:
        conn.execute(
            """INSERT INTO asset_instances(asset_id, file_id, source_id, path, role,
                                           quality_score, exists_at_scan)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(asset_id, path) DO UPDATE SET
                   file_id=excluded.file_id,
                   source_id=excluded.source_id,
                   role=excluded.role,
                   quality_score=excluded.quality_score,
                   exists_at_scan=excluded.exists_at_scan""",
            (asset_id, file_id, source_id, path, role, quality_score, 1 if exists_at_scan else 0)
        )
        row = conn.execute(
            "SELECT id FROM asset_instances WHERE asset_id=? AND path=?",
            (asset_id, path),
        ).fetchone()
        conn.execute(
            "UPDATE metadata_extractions SET asset_id = ? WHERE path = ? AND asset_id IS NULL",
            (asset_id, path),
        )
        if role == 'destination':
            mtime, size = _path_stats(path)
            _ensure_processing_state_conn(
                conn,
                asset_id=asset_id,
                instance_id=int(row['id']),
                path=path,
                processor='exiftool',
                source_mtime=mtime,
                source_size=size,
            )
        return int(row['id'])


def get_asset_instances(asset_id: int) -> list[sqlite3.Row]:
    """Return all known physical instances for an asset."""
    with _get_conn() as conn:
        return conn.execute(
            "SELECT * FROM asset_instances WHERE asset_id=? ORDER BY role, quality_score DESC",
            (asset_id,),
        ).fetchall()


def list_gallery_assets(limit: int = 80) -> list[dict]:
    """Return destination assets that make up the current vault gallery."""
    with _get_conn() as conn:
        rows = conn.execute(
            """WITH asset_meta AS (
                   SELECT asset_id,
                          COALESCE(
                            MAX(CASE WHEN extractor='exiftool' AND status='ok' THEN NULLIF(json_extract(raw_json, '$.device_name'), 'Desconhecido') END),
                            MAX(NULLIF(json_extract(raw_json, '$.device_name'), 'Desconhecido')),
                            MAX(json_extract(raw_json, '$.device_name')),
                            'Desconhecido'
                          ) AS device_name,
                          COALESCE(
                            MAX(CASE WHEN extractor='exiftool' AND status='ok' THEN NULLIF(NULLIF(json_extract(raw_json, '$.device_type'), ''), 'unknown') END),
                            MAX(NULLIF(NULLIF(json_extract(raw_json, '$.device_type'), ''), 'unknown')),
                            'unknown'
                          ) AS device_type,
                          COALESCE(MAX(CASE WHEN extractor='exiftool' AND status='ok' THEN NULLIF(json_extract(raw_json, '$.camera_make'), '') END), MAX(COALESCE(json_extract(raw_json, '$.camera_make'), ''))) AS camera_make,
                          COALESCE(MAX(CASE WHEN extractor='exiftool' AND status='ok' THEN NULLIF(json_extract(raw_json, '$.camera_model'), '') END), MAX(COALESCE(json_extract(raw_json, '$.camera_model'), ''))) AS camera_model,
                          COALESCE(MAX(CASE WHEN extractor='exiftool' AND status='ok' THEN NULLIF(json_extract(raw_json, '$.lens_model'), '') END), MAX(COALESCE(json_extract(raw_json, '$.lens_model'), ''))) AS lens_model,
                          COALESCE(MAX(CASE WHEN extractor='exiftool' AND status='ok' THEN NULLIF(json_extract(raw_json, '$.software'), '') END), MAX(COALESCE(json_extract(raw_json, '$.software'), ''))) AS software,
                          COALESCE(MAX(CASE WHEN extractor='exiftool' AND status='ok' THEN json_extract(raw_json, '$.gps_latitude') END), MAX(json_extract(raw_json, '$.gps_latitude'))) AS gps_latitude,
                          COALESCE(MAX(CASE WHEN extractor='exiftool' AND status='ok' THEN json_extract(raw_json, '$.gps_longitude') END), MAX(json_extract(raw_json, '$.gps_longitude'))) AS gps_longitude,
                          COALESCE(MAX(CASE WHEN extractor='exiftool' AND status='ok' THEN NULLIF(json_extract(raw_json, '$.exiftool.file_type'), '') END), MAX(COALESCE(json_extract(raw_json, '$.exiftool.file_type'), ''))) AS file_type,
                          COALESCE(MAX(CASE WHEN extractor='exiftool' AND status='ok' THEN NULLIF(json_extract(raw_json, '$.exiftool.mime_type'), '') END), MAX(COALESCE(json_extract(raw_json, '$.exiftool.mime_type'), ''))) AS mime_type,
                          COALESCE(MAX(CASE WHEN extractor='exiftool' AND status='ok' THEN NULLIF(json_extract(raw_json, '$.exiftool.codec'), '') END), MAX(COALESCE(json_extract(raw_json, '$.exiftool.codec'), ''))) AS codec,
                          COALESCE(MAX(CASE WHEN extractor='exiftool' AND status='ok' THEN NULLIF(json_extract(raw_json, '$.exiftool.bitrate'), '') END), MAX(COALESCE(json_extract(raw_json, '$.exiftool.bitrate'), ''))) AS bitrate,
                          COALESCE(MAX(CASE WHEN extractor='exiftool' AND status='ok' THEN json_extract(raw_json, '$.exiftool.frame_rate') END), MAX(json_extract(raw_json, '$.exiftool.frame_rate'))) AS frame_rate,
                          COALESCE(MAX(CASE WHEN extractor='exiftool' AND status='ok' THEN COALESCE(json_extract(raw_json, '$.iso'), json_extract(raw_json, '$.raw_exiftool.ISO')) END), MAX(COALESCE(json_extract(raw_json, '$.iso'), json_extract(raw_json, '$.raw_exiftool.ISO')))) AS iso,
                          COALESCE(MAX(CASE WHEN extractor='exiftool' AND status='ok' THEN COALESCE(json_extract(raw_json, '$.aperture'), json_extract(raw_json, '$.raw_exiftool.FNumber')) END), MAX(COALESCE(json_extract(raw_json, '$.aperture'), json_extract(raw_json, '$.raw_exiftool.FNumber')))) AS aperture,
                          COALESCE(MAX(CASE WHEN extractor='exiftool' AND status='ok' THEN COALESCE(json_extract(raw_json, '$.shutter_speed'), json_extract(raw_json, '$.raw_exiftool.ExposureTime')) END), MAX(COALESCE(json_extract(raw_json, '$.shutter_speed'), json_extract(raw_json, '$.raw_exiftool.ExposureTime')))) AS shutter_speed,
                          COALESCE(MAX(CASE WHEN extractor='exiftool' AND status='ok' THEN COALESCE(json_extract(raw_json, '$.focal_length'), json_extract(raw_json, '$.raw_exiftool.FocalLength')) END), MAX(COALESCE(json_extract(raw_json, '$.focal_length'), json_extract(raw_json, '$.raw_exiftool.FocalLength')))) AS focal_length,
                          MAX(CASE WHEN extractor = 'exiftool' AND status = 'ok' THEN extractor_version ELSE '' END) AS exiftool_version
                   FROM metadata_extractions
                   GROUP BY asset_id
               )
               SELECT
                   ai.id AS instance_id,
                   ai.path AS path,
                   ai.quality_score AS quality_score,
                   a.id AS asset_id,
                   a.sha256 AS sha256,
                   a.size AS size,
                   a.media_type AS media_type,
                   a.extension AS extension,
                   a.date_taken AS date_taken,
                   a.width AS width,
                   a.height AS height,
                   a.duration AS duration,
                   COALESCE(am.device_name, 'Desconhecido') AS device_name,
                   CASE
                     WHEN COALESCE(am.device_type, 'unknown') <> 'unknown' THEN am.device_type
                     WHEN lower(COALESCE(am.device_name, '')) LIKE '%dji%' OR lower(COALESCE(am.device_name, '')) LIKE '%drone%' THEN 'drone'
                     WHEN lower(COALESCE(am.device_name, '')) LIKE '%iphone%' OR lower(COALESCE(am.device_name, '')) LIKE '%samsung%' OR lower(COALESCE(am.device_name, '')) LIKE '%sm-%' THEN 'phone'
                     WHEN lower(COALESCE(am.device_name, '')) LIKE '%adobe%' OR lower(COALESCE(am.device_name, '')) LIKE '%lightroom%' THEN 'app'
                     WHEN lower(COALESCE(am.device_name, '')) LIKE '%canon%' OR lower(COALESCE(am.device_name, '')) LIKE '%nikon%' OR lower(COALESCE(am.device_name, '')) LIKE '%sony%' OR lower(COALESCE(am.device_name, '')) LIKE '%fujifilm%' OR lower(COALESCE(am.device_name, '')) LIKE '%gopro%' THEN 'camera'
                     ELSE 'unknown'
                   END AS device_type,
                   COALESCE(am.camera_make, '') AS camera_make,
                   COALESCE(am.camera_model, '') AS camera_model,
                   COALESCE(am.lens_model, '') AS lens_model,
                   COALESCE(am.software, '') AS software,
                   COALESCE(am.gps_latitude, '') AS gps_latitude,
                   COALESCE(am.gps_longitude, '') AS gps_longitude,
                   COALESCE(am.file_type, '') AS file_type,
                   COALESCE(am.mime_type, '') AS mime_type,
                   COALESCE(am.codec, '') AS codec,
                   COALESCE(am.bitrate, '') AS bitrate,
                   COALESCE(am.frame_rate, '') AS frame_rate,
                   COALESCE(am.iso, '') AS iso,
                   COALESCE(am.aperture, '') AS aperture,
                   COALESCE(am.shutter_speed, '') AS shutter_speed,
                   COALESCE(am.focal_length, '') AS focal_length,
                   COALESCE(am.exiftool_version, '') AS exiftool_version
               FROM asset_instances ai
               JOIN assets a ON a.id = ai.asset_id
               LEFT JOIN asset_meta am ON am.asset_id = a.id
               WHERE ai.role = 'destination'
               ORDER BY
                   CASE WHEN a.date_taken IS NULL THEN 1 ELSE 0 END,
                   a.date_taken DESC,
                   ai.id DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def _gallery_asset_select(where_sql: str = "", join_sql: str = "", order_sql: str = "", limit: int = 80,
                          params: Optional[list] = None) -> list[dict]:
    params = params or []
    with _get_conn() as conn:
        rows = conn.execute(
            f"""WITH asset_meta AS (
                   SELECT asset_id,
                          COALESCE(MAX(CASE WHEN extractor='exiftool' AND status='ok' THEN NULLIF(json_extract(raw_json, '$.device_name'), 'Desconhecido') END),
                                   MAX(NULLIF(json_extract(raw_json, '$.device_name'), 'Desconhecido')),
                                   MAX(json_extract(raw_json, '$.device_name')), 'Desconhecido') AS device_name,
                          COALESCE(MAX(CASE WHEN extractor='exiftool' AND status='ok' THEN NULLIF(NULLIF(json_extract(raw_json, '$.device_type'), ''), 'unknown') END),
                                   MAX(NULLIF(NULLIF(json_extract(raw_json, '$.device_type'), ''), 'unknown')), 'unknown') AS device_type,
                          COALESCE(MAX(CASE WHEN extractor='exiftool' AND status='ok' THEN NULLIF(json_extract(raw_json, '$.camera_make'), '') END), MAX(COALESCE(json_extract(raw_json, '$.camera_make'), ''))) AS camera_make,
                          COALESCE(MAX(CASE WHEN extractor='exiftool' AND status='ok' THEN NULLIF(json_extract(raw_json, '$.camera_model'), '') END), MAX(COALESCE(json_extract(raw_json, '$.camera_model'), ''))) AS camera_model,
                          COALESCE(MAX(CASE WHEN extractor='exiftool' AND status='ok' THEN NULLIF(json_extract(raw_json, '$.lens_model'), '') END), MAX(COALESCE(json_extract(raw_json, '$.lens_model'), ''))) AS lens_model,
                          COALESCE(MAX(CASE WHEN extractor='exiftool' AND status='ok' THEN NULLIF(json_extract(raw_json, '$.software'), '') END), MAX(COALESCE(json_extract(raw_json, '$.software'), ''))) AS software,
                          COALESCE(MAX(CASE WHEN extractor='exiftool' AND status='ok' THEN json_extract(raw_json, '$.gps_latitude') END), MAX(json_extract(raw_json, '$.gps_latitude'))) AS gps_latitude,
                          COALESCE(MAX(CASE WHEN extractor='exiftool' AND status='ok' THEN json_extract(raw_json, '$.gps_longitude') END), MAX(json_extract(raw_json, '$.gps_longitude'))) AS gps_longitude,
                          COALESCE(MAX(CASE WHEN extractor='exiftool' AND status='ok' THEN NULLIF(json_extract(raw_json, '$.exiftool.file_type'), '') END), MAX(COALESCE(json_extract(raw_json, '$.exiftool.file_type'), ''))) AS file_type,
                          COALESCE(MAX(CASE WHEN extractor='exiftool' AND status='ok' THEN NULLIF(json_extract(raw_json, '$.exiftool.mime_type'), '') END), MAX(COALESCE(json_extract(raw_json, '$.exiftool.mime_type'), ''))) AS mime_type,
                          COALESCE(MAX(CASE WHEN extractor='exiftool' AND status='ok' THEN NULLIF(json_extract(raw_json, '$.exiftool.codec'), '') END), MAX(COALESCE(json_extract(raw_json, '$.exiftool.codec'), ''))) AS codec,
                          COALESCE(MAX(CASE WHEN extractor='exiftool' AND status='ok' THEN NULLIF(json_extract(raw_json, '$.exiftool.bitrate'), '') END), MAX(COALESCE(json_extract(raw_json, '$.exiftool.bitrate'), ''))) AS bitrate,
                          COALESCE(MAX(CASE WHEN extractor='exiftool' AND status='ok' THEN json_extract(raw_json, '$.exiftool.frame_rate') END), MAX(json_extract(raw_json, '$.exiftool.frame_rate'))) AS frame_rate,
                          COALESCE(MAX(CASE WHEN extractor='exiftool' AND status='ok' THEN COALESCE(json_extract(raw_json, '$.iso'), json_extract(raw_json, '$.raw_exiftool.ISO')) END), MAX(COALESCE(json_extract(raw_json, '$.iso'), json_extract(raw_json, '$.raw_exiftool.ISO')))) AS iso,
                          COALESCE(MAX(CASE WHEN extractor='exiftool' AND status='ok' THEN COALESCE(json_extract(raw_json, '$.aperture'), json_extract(raw_json, '$.raw_exiftool.FNumber')) END), MAX(COALESCE(json_extract(raw_json, '$.aperture'), json_extract(raw_json, '$.raw_exiftool.FNumber')))) AS aperture,
                          COALESCE(MAX(CASE WHEN extractor='exiftool' AND status='ok' THEN COALESCE(json_extract(raw_json, '$.shutter_speed'), json_extract(raw_json, '$.raw_exiftool.ExposureTime')) END), MAX(COALESCE(json_extract(raw_json, '$.shutter_speed'), json_extract(raw_json, '$.raw_exiftool.ExposureTime')))) AS shutter_speed,
                          COALESCE(MAX(CASE WHEN extractor='exiftool' AND status='ok' THEN COALESCE(json_extract(raw_json, '$.focal_length'), json_extract(raw_json, '$.raw_exiftool.FocalLength')) END), MAX(COALESCE(json_extract(raw_json, '$.focal_length'), json_extract(raw_json, '$.raw_exiftool.FocalLength')))) AS focal_length,
                          MAX(CASE WHEN extractor = 'exiftool' AND status = 'ok' THEN extractor_version ELSE '' END) AS exiftool_version
                   FROM metadata_extractions
                   GROUP BY asset_id
               ),
               tag_meta AS (
                   SELECT at.asset_id,
                          GROUP_CONCAT(ct.label, ', ') AS tags
                   FROM asset_tags at
                   JOIN catalog_tags ct ON ct.id = at.tag_id
                   GROUP BY at.asset_id
               ),
               note_meta AS (
                   SELECT asset_id,
                          COUNT(*) AS note_count,
                          MAX(body) AS latest_note
                   FROM catalog_notes
                   GROUP BY asset_id
               )
               SELECT
                   ai.id AS instance_id,
                   ai.path AS path,
                   ai.quality_score AS quality_score,
                   a.id AS asset_id,
                   a.sha256 AS sha256,
                   a.size AS size,
                   a.media_type AS media_type,
                   a.extension AS extension,
                   a.date_taken AS date_taken,
                   a.width AS width,
                   a.height AS height,
                   a.duration AS duration,
                   COALESCE(am.device_name, 'Desconhecido') AS device_name,
                   CASE
                     WHEN COALESCE(am.device_type, 'unknown') <> 'unknown' THEN am.device_type
                     WHEN lower(COALESCE(am.device_name, '')) LIKE '%dji%' OR lower(COALESCE(am.device_name, '')) LIKE '%drone%' THEN 'drone'
                     WHEN lower(COALESCE(am.device_name, '')) LIKE '%iphone%' OR lower(COALESCE(am.device_name, '')) LIKE '%samsung%' OR lower(COALESCE(am.device_name, '')) LIKE '%sm-%' THEN 'phone'
                     WHEN lower(COALESCE(am.device_name, '')) LIKE '%adobe%' OR lower(COALESCE(am.device_name, '')) LIKE '%lightroom%' THEN 'app'
                     WHEN lower(COALESCE(am.device_name, '')) LIKE '%canon%' OR lower(COALESCE(am.device_name, '')) LIKE '%nikon%' OR lower(COALESCE(am.device_name, '')) LIKE '%sony%' OR lower(COALESCE(am.device_name, '')) LIKE '%fujifilm%' OR lower(COALESCE(am.device_name, '')) LIKE '%gopro%' THEN 'camera'
                     ELSE 'unknown'
                   END AS device_type,
                   COALESCE(am.camera_make, '') AS camera_make,
                   COALESCE(am.camera_model, '') AS camera_model,
                   COALESCE(am.lens_model, '') AS lens_model,
                   COALESCE(am.software, '') AS software,
                   COALESCE(am.gps_latitude, '') AS gps_latitude,
                   COALESCE(am.gps_longitude, '') AS gps_longitude,
                   COALESCE(am.file_type, '') AS file_type,
                   COALESCE(am.mime_type, '') AS mime_type,
                   COALESCE(am.codec, '') AS codec,
                   COALESCE(am.bitrate, '') AS bitrate,
                   COALESCE(am.frame_rate, '') AS frame_rate,
                   COALESCE(am.iso, '') AS iso,
                   COALESCE(am.aperture, '') AS aperture,
                   COALESCE(am.shutter_speed, '') AS shutter_speed,
                   COALESCE(am.focal_length, '') AS focal_length,
                   COALESCE(am.exiftool_version, '') AS exiftool_version,
                   COALESCE(tm.tags, '') AS tags,
                   COALESCE(nm.note_count, 0) AS note_count,
                   COALESCE(nm.latest_note, '') AS latest_note
               FROM asset_instances ai
               JOIN assets a ON a.id = ai.asset_id
               LEFT JOIN asset_meta am ON am.asset_id = a.id
               LEFT JOIN tag_meta tm ON tm.asset_id = a.id
               LEFT JOIN note_meta nm ON nm.asset_id = a.id
               {join_sql}
               WHERE ai.role = 'destination' {where_sql}
               {order_sql or "ORDER BY CASE WHEN a.date_taken IS NULL THEN 1 ELSE 0 END, a.date_taken DESC, ai.id DESC"}
               LIMIT ?""",
            [*params, limit],
        ).fetchall()
    return [dict(row) for row in rows]


def _fts_query(value: str) -> str:
    tokens = [token.strip().replace('"', '') for token in value.split() if token.strip()]
    return " ".join(f'"{token}"*' for token in tokens)


def search_gallery_assets(query: str, limit: int = 240) -> list[dict]:
    """Search destination gallery assets through FTS5 with LIKE fallback."""
    term = (query or '').strip()
    if not term:
        return list_gallery_assets(limit)
    try:
        return _gallery_asset_select(
            join_sql="JOIN catalog_search ON catalog_search.path = ai.path",
            where_sql="AND catalog_search MATCH ?",
            order_sql="ORDER BY bm25(catalog_search), CASE WHEN a.date_taken IS NULL THEN 1 ELSE 0 END, a.date_taken DESC",
            params=[_fts_query(term)],
            limit=limit,
        )
    except sqlite3.OperationalError:
        pattern = f"%{term.lower()}%"
        return _gallery_asset_select(
            where_sql="""AND (
                lower(ai.path) LIKE ?
                OR lower(COALESCE(a.extension, '')) LIKE ?
                OR lower(COALESCE(a.media_type, '')) LIKE ?
            )""",
            params=[pattern, pattern, pattern],
            limit=limit,
        )


def save_asset_tags(asset_id: int, labels: list[str], source: str = 'user') -> list[str]:
    cleaned = sorted({label.strip() for label in labels if label and label.strip()})
    with _get_conn() as conn:
        conn.execute("DELETE FROM asset_tags WHERE asset_id=? AND source=?", (asset_id, source))
        for label in cleaned:
            cur = conn.execute(
                "INSERT INTO catalog_tags(label, source) VALUES (?, ?) ON CONFLICT(label) DO UPDATE SET label=excluded.label",
                (label, source),
            )
            row = conn.execute("SELECT id FROM catalog_tags WHERE label=?", (label,)).fetchone()
            tag_id = int(row['id'] if row else cur.lastrowid)
            conn.execute(
                "INSERT OR REPLACE INTO asset_tags(asset_id, tag_id, confidence, source) VALUES (?, ?, ?, ?)",
                (asset_id, tag_id, 1.0, source),
            )
        rows = conn.execute("SELECT path, media_type, extension FROM asset_instances ai JOIN assets a ON a.id=ai.asset_id WHERE ai.asset_id=? AND ai.role='destination'", (asset_id,)).fetchall()
        for row in rows:
            refresh_catalog_search_conn(conn, row['path'], row['media_type'], row['extension'], tags=" ".join(cleaned))
    return cleaned


def add_catalog_note(asset_id: int, body: str, note_type: str = 'note', source: str = 'user') -> int:
    text = (body or '').strip()
    if not text:
        raise ValueError('Nota obrigatoria')
    with _get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO catalog_notes(asset_id, note_type, source, body) VALUES (?, ?, ?, ?)",
            (asset_id, note_type, source, text),
        )
        return int(cur.lastrowid)


def get_asset_catalog(asset_id: int) -> dict:
    with _get_conn() as conn:
        tags = conn.execute(
            """SELECT ct.label FROM asset_tags at
               JOIN catalog_tags ct ON ct.id = at.tag_id
               WHERE at.asset_id=?
               ORDER BY ct.label""",
            (asset_id,),
        ).fetchall()
        notes = conn.execute(
            "SELECT id, note_type, source, body, created_at FROM catalog_notes WHERE asset_id=? ORDER BY created_at DESC, id DESC LIMIT 20",
            (asset_id,),
        ).fetchall()
    return {'assetId': asset_id, 'tags': [row['label'] for row in tags], 'notes': [dict(row) for row in notes]}


def gallery_health() -> dict:
    with _get_conn() as conn:
        row = conn.execute(
            """SELECT
                   COUNT(*) AS total,
                   SUM(CASE WHEN a.date_taken IS NULL THEN 1 ELSE 0 END) AS without_date,
                   SUM(CASE WHEN COALESCE(a.media_type, '') = 'video' AND a.size >= ? THEN 1 ELSE 0 END) AS large_videos,
                   SUM(CASE WHEN ai.path IS NULL OR ai.path = '' THEN 1 ELSE 0 END) AS missing_path
               FROM asset_instances ai
               JOIN assets a ON a.id = ai.asset_id
               WHERE ai.role='destination'""",
            (50 * 1024 * 1024,),
        ).fetchone()
        processing = conn.execute(
            "SELECT status, COUNT(*) AS count FROM asset_processing_state WHERE processor='exiftool' GROUP BY status",
        ).fetchall()
        open_imports = conn.execute(
            """SELECT COUNT(*) AS count
               FROM imports
               WHERE status IN ('created', 'scanning', 'analyzed', 'running', 'failed')""",
        ).fetchone()
    processing_counts = {item['status']: item['count'] for item in processing}
    return {
        'total': row['total'] or 0,
        'withoutDate': row['without_date'] or 0,
        'largeVideos': row['large_videos'] or 0,
        'missingPath': row['missing_path'] or 0,
        'metadataPending': sum(processing_counts.get(key, 0) for key in ('pending', 'stale', 'error')),
        'openImports': open_imports['count'] or 0,
        'processing': processing_counts,
    }


def resumable_imports(limit: int = 10) -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute(
            """SELECT i.id, i.name, i.source_path, i.status, i.ingest_plan_id,
                      COUNT(io.id) AS operations,
                      SUM(CASE WHEN io.status IN ('planned', 'error', 'running') AND io.action IN ('copy', 'move') THEN 1 ELSE 0 END) AS resumable,
                      SUM(CASE WHEN io.status = 'done' THEN 1 ELSE 0 END) AS done,
                      SUM(CASE WHEN io.status = 'error' THEN 1 ELSE 0 END) AS errors
               FROM imports i
               JOIN ingest_plans ip ON ip.id = i.ingest_plan_id
               JOIN ingest_operations io ON io.plan_id = ip.id
               WHERE i.ingest_plan_id IS NOT NULL
               GROUP BY i.id
               HAVING resumable > 0 OR i.status IN ('failed', 'running', 'analyzed')
               ORDER BY i.created_at DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def job_summary() -> dict:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT kind, status, COUNT(*) AS count FROM background_jobs GROUP BY kind, status",
        ).fetchall()
    summary: dict[str, dict[str, int]] = {}
    for row in rows:
        summary.setdefault(row['kind'], {})[row['status']] = row['count']
    return summary


def gallery_totals() -> dict:
    """Return aggregate counts for destination assets."""
    with _get_conn() as conn:
        row = conn.execute(
            """SELECT
                   COUNT(*) AS total,
                   COALESCE(SUM(a.size), 0) AS bytes_total,
                   SUM(CASE WHEN a.media_type = 'photo' THEN 1 ELSE 0 END) AS photos,
                   SUM(CASE WHEN a.media_type = 'video' THEN 1 ELSE 0 END) AS videos,
                   COALESCE(SUM(CASE WHEN a.media_type = 'photo' THEN a.size ELSE 0 END), 0) AS photo_bytes,
                   COALESCE(SUM(CASE WHEN a.media_type = 'video' THEN a.size ELSE 0 END), 0) AS video_bytes,
                   SUM(CASE WHEN a.date_taken IS NULL THEN 1 ELSE 0 END) AS without_date,
                   MIN(a.date_taken) AS first_date,
                   MAX(a.date_taken) AS last_date,
                   COUNT(DISTINCT strftime('%Y', a.date_taken)) AS year_count,
                   COUNT(DISTINCT strftime('%Y-%m', a.date_taken)) AS month_count,
                   COUNT(DISTINCT a.extension) AS extension_count
               FROM asset_instances ai
               JOIN assets a ON a.id = ai.asset_id
               WHERE ai.role = 'destination'"""
        ).fetchone()
    return {
        'total': row['total'] or 0,
        'bytes_total': row['bytes_total'] or 0,
        'photos': row['photos'] or 0,
        'videos': row['videos'] or 0,
        'photo_bytes': row['photo_bytes'] or 0,
        'video_bytes': row['video_bytes'] or 0,
        'without_date': row['without_date'] or 0,
        'first_date': row['first_date'],
        'last_date': row['last_date'],
        'year_count': row['year_count'] or 0,
        'month_count': row['month_count'] or 0,
        'extension_count': row['extension_count'] or 0,
    }


def duplicate_savings_total() -> dict:
    """Return cumulative storage avoided by duplicate decisions."""
    with _get_conn() as conn:
        row = conn.execute(
            """SELECT COUNT(*) AS duplicate_count,
                      COALESCE(SUM(size), 0) AS duplicate_bytes
               FROM import_files
               WHERE reason IN (
                   'exact_duplicate_in_plan',
                   'exact_duplicate_in_vault',
                   'known_asset_in_vault'
               )
                 AND status IN ('skipped', 'done')"""
        ).fetchone()
    return {
        'count': row['duplicate_count'] or 0,
        'bytes': row['duplicate_bytes'] or 0,
    }


def gallery_month_timeline(limit: int = 120) -> list[dict]:
    """Return chronological monthly gallery production buckets."""
    with _get_conn() as conn:
        rows = conn.execute(
            """SELECT COALESCE(strftime('%Y-%m', a.date_taken), 'Sem data') AS label,
                      COUNT(*) AS count,
                      SUM(CASE WHEN a.media_type = 'photo' THEN 1 ELSE 0 END) AS photos,
                      SUM(CASE WHEN a.media_type = 'video' THEN 1 ELSE 0 END) AS videos,
                      COALESCE(SUM(a.size), 0) AS bytes
               FROM asset_instances ai
               JOIN assets a ON a.id = ai.asset_id
               WHERE ai.role = 'destination'
               GROUP BY label
               ORDER BY label ASC
               LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def gallery_breakdowns(limit: int = 8) -> dict:
    """Return grouped gallery facets for cockpit-style summaries."""
    with _get_conn() as conn:
        media = conn.execute(
            """SELECT COALESCE(a.media_type, 'other') AS label,
                      COUNT(*) AS count,
                      COALESCE(SUM(a.size), 0) AS bytes
               FROM asset_instances ai
               JOIN assets a ON a.id = ai.asset_id
               WHERE ai.role = 'destination'
               GROUP BY COALESCE(a.media_type, 'other')
               ORDER BY count DESC"""
        ).fetchall()
        years = conn.execute(
            """SELECT COALESCE(strftime('%Y', a.date_taken), 'Sem data') AS label,
                      COUNT(*) AS count,
                      COALESCE(SUM(a.size), 0) AS bytes
               FROM asset_instances ai
               JOIN assets a ON a.id = ai.asset_id
               WHERE ai.role = 'destination'
               GROUP BY label
               ORDER BY label DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        months = conn.execute(
            """SELECT COALESCE(strftime('%Y-%m', a.date_taken), 'Sem data') AS label,
                      COUNT(*) AS count,
                      COALESCE(SUM(a.size), 0) AS bytes
               FROM asset_instances ai
               JOIN assets a ON a.id = ai.asset_id
               WHERE ai.role = 'destination'
               GROUP BY label
               ORDER BY label DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        extensions = conn.execute(
            """SELECT COALESCE(a.extension, 'sem extensao') AS label,
                      COUNT(*) AS count,
                      COALESCE(SUM(a.size), 0) AS bytes
               FROM asset_instances ai
               JOIN assets a ON a.id = ai.asset_id
               WHERE ai.role = 'destination'
               GROUP BY COALESCE(a.extension, 'sem extensao')
               ORDER BY count DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        devices = conn.execute(
            """WITH asset_meta AS (
                   SELECT asset_id,
                          COALESCE(
                            MAX(NULLIF(json_extract(raw_json, '$.device_name'), 'Desconhecido')),
                            MAX(json_extract(raw_json, '$.device_name')),
                            'Desconhecido'
                          ) AS label
                   FROM metadata_extractions
                   GROUP BY asset_id
               )
               SELECT COALESCE(am.label, 'Desconhecido') AS label,
                      COUNT(*) AS count,
                      COALESCE(SUM(a.size), 0) AS bytes
               FROM asset_instances ai
               JOIN assets a ON a.id = ai.asset_id
               LEFT JOIN asset_meta am ON am.asset_id = a.id
               WHERE ai.role = 'destination'
               GROUP BY label
               ORDER BY count DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        device_types = conn.execute(
            """WITH asset_meta AS (
                   SELECT asset_id,
                          COALESCE(
                            MAX(NULLIF(json_extract(raw_json, '$.device_name'), 'Desconhecido')),
                            MAX(json_extract(raw_json, '$.device_name')),
                            ''
                          ) AS device_name,
                          COALESCE(
                            MAX(NULLIF(NULLIF(json_extract(raw_json, '$.device_type'), ''), 'unknown')),
                            'unknown'
                          ) AS device_type
                   FROM metadata_extractions
                   GROUP BY asset_id
               ),
               typed AS (
                   SELECT a.id AS asset_id,
                          a.size AS size,
                          CASE
                            WHEN COALESCE(am.device_type, 'unknown') <> 'unknown' THEN am.device_type
                            WHEN lower(COALESCE(am.device_name, '')) LIKE '%dji%' OR lower(COALESCE(am.device_name, '')) LIKE '%drone%' THEN 'drone'
                            WHEN lower(COALESCE(am.device_name, '')) LIKE '%iphone%' OR lower(COALESCE(am.device_name, '')) LIKE '%samsung%' OR lower(COALESCE(am.device_name, '')) LIKE '%sm-%' THEN 'phone'
                            WHEN lower(COALESCE(am.device_name, '')) LIKE '%adobe%' OR lower(COALESCE(am.device_name, '')) LIKE '%lightroom%' THEN 'app'
                            WHEN lower(COALESCE(am.device_name, '')) LIKE '%canon%' OR lower(COALESCE(am.device_name, '')) LIKE '%nikon%' OR lower(COALESCE(am.device_name, '')) LIKE '%sony%' OR lower(COALESCE(am.device_name, '')) LIKE '%fujifilm%' OR lower(COALESCE(am.device_name, '')) LIKE '%gopro%' THEN 'camera'
                            ELSE 'unknown'
                          END AS label
                   FROM asset_instances ai
                   JOIN assets a ON a.id = ai.asset_id
                   LEFT JOIN asset_meta am ON am.asset_id = a.id
                   WHERE ai.role = 'destination'
               )
               SELECT label,
                      COUNT(*) AS count,
                      COALESCE(SUM(size), 0) AS bytes
               FROM typed
               GROUP BY label
               ORDER BY count DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        cameras = conn.execute(
            """WITH asset_meta AS (
                   SELECT asset_id,
                          COALESCE(
                            NULLIF(MAX(TRIM(
                              CASE
                                WHEN lower(COALESCE(json_extract(raw_json, '$.camera_make'), '')) LIKE '%dji%' THEN 'DJI'
                                WHEN upper(COALESCE(json_extract(raw_json, '$.camera_model'), '')) LIKE 'FC%' THEN 'DJI'
                                ELSE COALESCE(json_extract(raw_json, '$.camera_make'), '')
                              END || ' ' ||
                              CASE
                                WHEN upper(COALESCE(json_extract(raw_json, '$.camera_model'), '')) LIKE 'DJI %'
                                  THEN substr(COALESCE(json_extract(raw_json, '$.camera_model'), ''), 5)
                                ELSE COALESCE(json_extract(raw_json, '$.camera_model'), '')
                              END
                            )), ''),
                            COALESCE(
                              MAX(NULLIF(json_extract(raw_json, '$.device_name'), 'Desconhecido')),
                              MAX(json_extract(raw_json, '$.device_name')),
                              ''
                            )
                          ) AS label
                   FROM metadata_extractions
                   GROUP BY asset_id
               )
               SELECT am.label AS label,
                      COUNT(*) AS count,
                      COALESCE(SUM(a.size), 0) AS bytes
               FROM asset_instances ai
               JOIN assets a ON a.id = ai.asset_id
               LEFT JOIN asset_meta am ON am.asset_id = a.id
               WHERE ai.role = 'destination'
                 AND am.label <> ''
                 AND am.label <> 'Desconhecido'
               GROUP BY am.label
               ORDER BY count DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()

    def rows(values):
        return [{'label': row['label'], 'count': row['count'] or 0, 'bytes': row['bytes'] or 0} for row in values]

    return {
        'media': rows(media),
        'years': rows(years),
        'months': rows(months),
        'extensions': rows(extensions),
        'devices': rows(devices),
        'deviceTypes': rows(device_types),
        'cameras': rows(cameras),
    }


def create_ingest_plan(vault_id: int, mode: str = 'copy', summary: Optional[dict] = None) -> int:
    """Create a persisted ingest plan."""
    with _get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO ingest_plans(vault_id, mode, status, summary) VALUES (?, ?, ?, ?)",
            (vault_id, mode, 'planned', json.dumps(summary or {})),
        )
        return cur.lastrowid


def set_ingest_plan_import(plan_id: int, import_id: int) -> None:
    with _get_conn() as conn:
        conn.execute("UPDATE ingest_plans SET import_id=? WHERE id=?", (import_id, plan_id))


def create_import(vault_id: int, name: str, source_path: str,
                  status: str = 'created', summary: Optional[dict] = None) -> int:
    with _get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO imports(vault_id, name, source_path, status, summary)
               VALUES (?, ?, ?, ?, ?)""",
            (vault_id, name, source_path, status, json.dumps(summary or {})),
        )
        return cur.lastrowid


def update_import_status(import_id: int, status: str) -> None:
    now = datetime.now().isoformat()
    fields = ["status=?"]
    params: list = [status]
    if status in {'scanning', 'running'}:
        fields.append("started_at=COALESCE(started_at, ?)")
        params.append(now)
    if status == 'analyzed':
        fields.append("analyzed_at=?")
        params.append(now)
    if status in {'completed', 'failed', 'cancelled'}:
        fields.append("completed_at=?")
        params.append(now)
    params.append(import_id)
    with _get_conn() as conn:
        conn.execute(f"UPDATE imports SET {', '.join(fields)} WHERE id=?", params)


def set_import_plan(import_id: int, ingest_plan_id: int) -> None:
    with _get_conn() as conn:
        conn.execute("UPDATE imports SET ingest_plan_id=? WHERE id=?", (ingest_plan_id, import_id))


def update_import_summary(import_id: int, summary: dict) -> None:
    allowed = {
        'files_found', 'files_new', 'files_duplicate', 'files_existing',
        'files_review', 'files_imported', 'files_skipped', 'files_error',
        'bytes_found', 'bytes_new', 'bytes_imported',
    }
    fields = []
    params = []
    for key, value in summary.items():
        if key in allowed:
            fields.append(f"{key}=?")
            params.append(value)
    if 'summary' in summary:
        fields.append("summary=?")
        params.append(json.dumps(summary['summary'] or {}))
    if not fields:
        return
    params.append(import_id)
    with _get_conn() as conn:
        conn.execute(f"UPDATE imports SET {', '.join(fields)} WHERE id=?", params)


def add_import_file(import_id: int, file_data: dict) -> int:
    date_taken = file_data.get('date_taken')
    date_str = date_taken.isoformat() if hasattr(date_taken, 'isoformat') else date_taken
    with _get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO import_files(
                   import_id, ingest_operation_id, asset_id, src_path, dst_path,
                   sha256, status, decision, reason, size, media_type, extension,
                   date_taken, error
               )
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                import_id,
                file_data.get('ingest_operation_id'),
                file_data.get('asset_id'),
                file_data['src_path'],
                file_data.get('dst_path'),
                file_data.get('sha256'),
                file_data.get('status', 'planned'),
                file_data.get('decision'),
                file_data.get('reason'),
                file_data.get('size'),
                file_data.get('media_type'),
                file_data.get('extension'),
                date_str,
                file_data.get('error'),
            ),
        )
        row = conn.execute(
            "SELECT id FROM import_files WHERE import_id=? AND src_path=?",
            (import_id, file_data['src_path']),
        ).fetchone()
        return int(row['id'])


def update_import_file_status(import_id: int, src_path: str, status: str,
                              error: Optional[str] = None) -> None:
    now = datetime.now().isoformat()
    with _get_conn() as conn:
        conn.execute(
            """UPDATE import_files
               SET status=?, error=?, completed_at=CASE WHEN ? IN ('done', 'skipped', 'error') THEN ? ELSE completed_at END
               WHERE import_id=? AND src_path=?""",
            (status, error, status, now, import_id, src_path),
        )


def update_import_file_decision(file_id: int, decision: str, status: Optional[str] = None) -> None:
    """Update a file decision and keep the linked ingest operation executable."""
    action = {'import': 'copy', 'skip': 'skip', 'review': 'skip'}.get(decision, decision)
    file_status = status or ('planned' if decision == 'import' else 'skipped' if decision == 'skip' else 'review')
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT ingest_operation_id FROM import_files WHERE id=?",
            (file_id,),
        ).fetchone()
        conn.execute(
            "UPDATE import_files SET decision=?, status=? WHERE id=?",
            (action, file_status, file_id),
        )
        if row and row['ingest_operation_id']:
            op_status = 'planned' if action in {'copy', 'move'} else 'skipped'
            conn.execute(
                "UPDATE ingest_operations SET action=?, status=? WHERE id=?",
                (action, op_status, row['ingest_operation_id']),
            )


def list_imports(limit: int = 50) -> list[dict]:
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM imports ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_import(import_id: int) -> Optional[sqlite3.Row]:
    with _get_conn() as conn:
        return conn.execute("SELECT * FROM imports WHERE id=?", (import_id,)).fetchone()


def get_import_files(import_id: int, limit: int = 500, reason: Optional[str] = None) -> list[dict]:
    params: list = [import_id]
    where = "import_id=?"
    if reason:
        where += " AND reason=?"
        params.append(reason)
    params.append(limit)
    with _get_conn() as conn:
        rows = conn.execute(
            f"""SELECT * FROM import_files
                WHERE {where}
                ORDER BY
                    CASE reason
                        WHEN 'new_asset' THEN 0
                        WHEN 'exact_duplicate_in_plan' THEN 1
                        WHEN 'exact_duplicate_in_vault' THEN 2
                        ELSE 3
                    END,
                    size DESC
                LIMIT ?""",
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def summarize_import_decisions(import_id: int) -> dict:
    """Return grouped decision data for an import without loading every file row."""
    with _get_conn() as conn:
        by_reason = conn.execute(
            """SELECT COALESCE(reason, 'unknown') AS label,
                      COALESCE(decision, 'review') AS decision,
                      COALESCE(media_type, 'media') AS media_type,
                      COALESCE(status, 'planned') AS status,
                      COUNT(*) AS count,
                      COALESCE(SUM(size), 0) AS bytes
               FROM import_files
               WHERE import_id=?
               GROUP BY label, decision, media_type, status
               ORDER BY count DESC""",
            (import_id,),
        ).fetchall()
        by_media = conn.execute(
            """SELECT COALESCE(media_type, 'media') AS label,
                      COUNT(*) AS count,
                      COALESCE(SUM(size), 0) AS bytes
               FROM import_files
               WHERE import_id=?
               GROUP BY COALESCE(media_type, 'media')
               ORDER BY count DESC""",
            (import_id,),
        ).fetchall()
        by_status = conn.execute(
            """SELECT COALESCE(status, 'planned') AS label,
                      COUNT(*) AS count,
                      COALESCE(SUM(size), 0) AS bytes
               FROM import_files
               WHERE import_id=?
               GROUP BY COALESCE(status, 'planned')
               ORDER BY count DESC""",
            (import_id,),
        ).fetchall()

    def rows(values):
        return [{'label': row['label'], 'count': row['count'] or 0, 'bytes': row['bytes'] or 0} for row in values]

    return {
        'reasonGroups': [dict(row) for row in by_reason],
        'mediaGroups': rows(by_media),
        'statusGroups': rows(by_status),
    }


def get_import_by_plan(plan_id: int) -> Optional[sqlite3.Row]:
    with _get_conn() as conn:
        return conn.execute("SELECT * FROM imports WHERE ingest_plan_id=?", (plan_id,)).fetchone()


def add_ingest_operation(plan_id: int, operation: dict) -> int:
    """Persist a planned ingest operation and return its id."""
    with _get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO ingest_operations(
                   plan_id, asset_id, src_path, dst_path, action, reason,
                   status, error, sha256, size
               )
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                plan_id,
                operation.get('asset_id'),
                operation['src_path'],
                operation['dst_path'],
                operation['action'],
                operation.get('reason'),
                operation.get('status', 'planned'),
                operation.get('error'),
                operation.get('sha256'),
                operation.get('size'),
            ),
        )
        row = conn.execute(
            """SELECT id FROM ingest_operations
               WHERE plan_id=? AND src_path=? AND dst_path=?""",
            (plan_id, operation['src_path'], operation['dst_path']),
        ).fetchone()
        return int(row['id'])


def get_ingest_operations(plan_id: int) -> list[sqlite3.Row]:
    """Return persisted operations for an ingest plan."""
    with _get_conn() as conn:
        return conn.execute(
            "SELECT * FROM ingest_operations WHERE plan_id=? ORDER BY id",
            (plan_id,),
        ).fetchall()


def update_ingest_plan_status(plan_id: int, status: str) -> None:
    """Update ingest plan lifecycle fields."""
    now = datetime.now().isoformat()
    with _get_conn() as conn:
        if status == 'running':
            conn.execute(
                "UPDATE ingest_plans SET status=?, started_at=COALESCE(started_at, ?) WHERE id=?",
                (status, now, plan_id),
            )
        elif status in {'completed', 'error', 'cancelled'}:
            conn.execute(
                "UPDATE ingest_plans SET status=?, completed_at=? WHERE id=?",
                (status, now, plan_id),
            )
        else:
            conn.execute("UPDATE ingest_plans SET status=? WHERE id=?", (status, plan_id))


def update_ingest_operation_status(operation_id: int, status: str,
                                   error: Optional[str] = None) -> None:
    """Update a persisted ingest operation status."""
    now = datetime.now().isoformat()
    with _get_conn() as conn:
        if status == 'running':
            conn.execute(
                """UPDATE ingest_operations
                   SET status=?, error=?, started_at=COALESCE(started_at, ?)
                   WHERE id=?""",
                (status, error, now, operation_id),
            )
        elif status in {'done', 'skipped', 'error'}:
            conn.execute(
                """UPDATE ingest_operations
                   SET status=?, error=?, completed_at=?
                   WHERE id=?""",
                (status, error, now, operation_id),
            )
        else:
            conn.execute(
                "UPDATE ingest_operations SET status=?, error=? WHERE id=?",
                (status, error, operation_id),
            )


def save_audit_event(entity_type: str, entity_id: Optional[int], event_type: str,
                     message: Optional[str] = None, payload: Optional[dict] = None) -> int:
    """Append an audit event."""
    with _get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO audit_events(entity_type, entity_id, event_type, message, payload)
               VALUES (?, ?, ?, ?, ?)""",
            (entity_type, entity_id, event_type, message, json.dumps(payload or {})),
        )
        return cur.lastrowid
