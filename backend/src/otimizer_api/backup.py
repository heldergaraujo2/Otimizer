"""Provider-neutral SQLite backup, integrity validation and restore helpers.

Backups are SQLite database snapshots plus a JSON manifest containing integrity
metadata. The helpers never expose or log secrets. Operational restore should
be followed by session invalidation/re-authentication at the application layer.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

FORMAT_VERSION = 1
EXPECTED_TABLES = {"accounts", "sessions", "licenses", "license_events", "payments"}


class BackupError(RuntimeError):
    """Raised when a backup or restore operation cannot be trusted."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_sqlite(path: Path) -> None:
    if not path.is_file() or path.stat().st_size == 0:
        raise BackupError("backup database is missing or empty")
    try:
        with sqlite3.connect(path) as connection:
            result = connection.execute("PRAGMA integrity_check").fetchone()
            if not result or result[0] != "ok":
                raise BackupError("SQLite integrity_check failed")
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
    except sqlite3.DatabaseError as exc:
        raise BackupError("backup is not a valid SQLite database") from exc
    missing = EXPECTED_TABLES - tables
    if missing:
        raise BackupError(f"backup is missing critical tables: {sorted(missing)}")


def _counts(path: Path) -> dict[str, int]:
    with sqlite3.connect(path) as connection:
        return {
            table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in sorted(EXPECTED_TABLES)
        }


def create_backup(database_path: str | Path, backup_path: str | Path) -> Path:
    """Create and validate an atomic SQLite snapshot and its JSON manifest."""
    source = Path(database_path)
    destination = Path(backup_path)
    if source.resolve() == destination.resolve():
        raise BackupError("backup destination must differ from source database")
    if not source.is_file():
        raise BackupError("source database does not exist")
    destination.parent.mkdir(parents=True, exist_ok=True)
    manifest_path = destination.with_suffix(destination.suffix + ".json")

    with tempfile.NamedTemporaryFile(
        dir=destination.parent, prefix=f".{destination.name}.", suffix=".tmp", delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)
    manifest_tmp = manifest_path.with_suffix(manifest_path.suffix + ".tmp")
    try:
        with sqlite3.connect(source) as source_connection, sqlite3.connect(temporary_path) as target_connection:
            source_connection.backup(target_connection)
        _validate_sqlite(temporary_path)
        os.chmod(temporary_path, 0o600)
        digest = _sha256(temporary_path)
        manifest = {
            "format_version": FORMAT_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "sha256": digest,
            "size_bytes": temporary_path.stat().st_size,
            "tables": _counts(temporary_path),
        }
        os.replace(temporary_path, destination)
        manifest_tmp.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.chmod(manifest_tmp, 0o600)
        os.replace(manifest_tmp, manifest_path)
        return destination
    except Exception:
        temporary_path.unlink(missing_ok=True)
        manifest_tmp.unlink(missing_ok=True)
        raise


def validate_backup(backup_path: str | Path) -> dict[str, object]:
    """Validate manifest, digest and SQLite integrity; return the manifest."""
    backup = Path(backup_path)
    manifest_path = backup.with_suffix(backup.suffix + ".json")
    if not manifest_path.is_file():
        raise BackupError("backup manifest is missing")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BackupError("backup manifest is unreadable") from exc
    if manifest.get("format_version") != FORMAT_VERSION:
        raise BackupError("unsupported backup format version")
    expected = manifest.get("sha256")
    if not isinstance(expected, str) or _sha256(backup) != expected:
        raise BackupError("backup SHA-256 does not match its manifest")
    _validate_sqlite(backup)
    actual_counts = _counts(backup)
    if manifest.get("tables") != actual_counts:
        raise BackupError("backup table counts do not match its manifest")
    return manifest


def restore_backup(backup_path: str | Path, target_path: str | Path) -> Path:
    """Validate a backup and atomically restore it to a new SQLite path.

    Existing target files are replaced only after the validated snapshot has
    been copied and checked.
    """
    backup = Path(backup_path)
    target = Path(target_path)
    if backup.resolve() == target.resolve():
        raise BackupError("restore target must differ from backup file")
    validate_backup(backup)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=target.parent, prefix=f".{target.name}.", suffix=".restore", delete=False
    ) as temporary:
        temporary_path = Path(temporary.name)
    try:
        with sqlite3.connect(backup) as source_connection, sqlite3.connect(temporary_path) as target_connection:
            source_connection.backup(target_connection)
        _validate_sqlite(temporary_path)
        if _sha256(temporary_path) != _sha256(backup):
            raise BackupError("restored database digest differs from validated backup")
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, target)
        return target
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def prune_backups(directory: str | Path, keep: int = 7, pattern: str = "*.db") -> list[Path]:
    """Delete only validated backup snapshots beyond the retention count.

    Invalid snapshots are retained for investigation instead of being silently
    deleted. The paired manifest is removed only after its database is removed.
    """
    if keep < 1:
        raise ValueError("keep must be at least 1")
    root = Path(directory)
    if not root.is_dir():
        return []
    candidates: list[tuple[Path, float]] = []
    for path in root.glob(pattern):
        if not path.is_file() or path.name.endswith(".tmp"):
            continue
        try:
            validate_backup(path)
        except BackupError:
            continue
        candidates.append((path, path.stat().st_mtime))
    candidates.sort(key=lambda item: item[1], reverse=True)
    removed: list[Path] = []
    for path, _ in candidates[keep:]:
        path.unlink()
        path.with_suffix(path.suffix + ".json").unlink(missing_ok=True)
        removed.append(path)
    return removed
