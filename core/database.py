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
        """)
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
        ]:
            try:
                conn.execute(idx_sql)
            except Exception:
                pass


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
        return int(row['id'])


def get_asset_instances(asset_id: int) -> list[sqlite3.Row]:
    """Return all known physical instances for an asset."""
    with _get_conn() as conn:
        return conn.execute(
            "SELECT * FROM asset_instances WHERE asset_id=? ORDER BY role, quality_score DESC",
            (asset_id,),
        ).fetchall()


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
