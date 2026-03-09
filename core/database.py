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
                scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
            CREATE INDEX IF NOT EXISTS idx_hash ON files(hash_sha256);
            CREATE INDEX IF NOT EXISTS idx_phash ON files(hash_phash);
            CREATE INDEX IF NOT EXISTS idx_path ON files(path);
            CREATE INDEX IF NOT EXISTS idx_dest_hash ON destination_index(destination, sha256);
            CREATE INDEX IF NOT EXISTS idx_dest_size ON destination_index(destination, size);
        """)
        # Migrate: add new columns if they don't exist yet
        for col_sql in [
            "ALTER TABLE sessions ADD COLUMN errors INTEGER DEFAULT 0",
            "ALTER TABLE sessions ADD COLUMN total_files INTEGER DEFAULT 0",
            "ALTER TABLE sessions ADD COLUMN status TEXT DEFAULT 'completed'",
        ]:
            try:
                conn.execute(col_sql)
            except Exception:
                pass


def save_file_record(path: str, hash_sha256: Optional[str], hash_phash: Optional[str],
                     date_taken: Optional[datetime], size: int, media_type: str,
                     extension: str, mtime: float) -> None:
    """Insert or update file record."""
    date_str = date_taken.isoformat() if date_taken else None
    with _get_conn() as conn:
        conn.execute("""
            INSERT INTO files (path, hash_sha256, hash_phash, date_taken, size,
                               media_type, extension, mtime, scanned_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(path) DO UPDATE SET
                hash_sha256=excluded.hash_sha256,
                hash_phash=excluded.hash_phash,
                date_taken=excluded.date_taken,
                size=excluded.size,
                media_type=excluded.media_type,
                extension=excluded.extension,
                mtime=excluded.mtime,
                scanned_at=CURRENT_TIMESTAMP
        """, (path, hash_sha256, hash_phash, date_str, size, media_type, extension, mtime))


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


def clear_file_records() -> None:
    """Remove all file records (for fresh scan)."""
    with _get_conn() as conn:
        conn.execute("DELETE FROM files")


def get_files_by_year() -> dict[int, int]:
    """Return {year: count} for all files with a date_taken."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT strftime('%Y', date_taken) as yr, COUNT(*) as cnt "
            "FROM files WHERE date_taken IS NOT NULL GROUP BY yr ORDER BY yr"
        ).fetchall()
    return {int(row['yr']): row['cnt'] for row in rows if row['yr']}


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
