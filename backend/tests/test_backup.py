from __future__ import annotations

import json
import os
import sqlite3

import pytest

from otimizer_api.backup import BackupError, create_backup, prune_backups, restore_backup, validate_backup
from otimizer_api.persistence import SQLiteDatabase


def _seed_database(path):
    database = SQLiteDatabase(path)
    with database.connect() as connection:
        connection.execute(
            "INSERT INTO accounts(account_id,email,password_hash,active,role) VALUES (?,?,?,?,?)",
            ("acct-1", "owner@example.test", "password-hash", 1, "ADMIN"),
        )
        connection.execute(
            "INSERT INTO sessions(session_id,account_id,token_hash,expires_at) VALUES (?,?,?,?)",
            ("sess-1", "acct-1", "token-hash", "2026-10-01T00:00:00+00:00"),
        )
        connection.execute(
            "INSERT INTO licenses(license_id,account_id,starts_at,expires_at,license_key,status,plan) VALUES (?,?,?,?,?,?,?)",
            ("lic-1", "acct-1", "2026-09-01T00:00:00+00:00", "2026-10-01T00:00:00+00:00", "KEY-1", "ATIVA", "pro"),
        )
        connection.execute(
            "INSERT INTO license_events(event_id,license_id,action,occurred_at) VALUES (?,?,?,?)",
            ("evt-1", "lic-1", "CREATED", "2026-09-01T00:00:00+00:00"),
        )
        connection.execute(
            "INSERT INTO payments(payment_id,account_id,license_id,amount_cents,expires_at,pix_copy_paste,status) VALUES (?,?,?,?,?,?,?)",
            ("pay-1", "acct-1", "lic-1", 2990, "2026-09-17T13:00:00+00:00", "pix-test-payload", "CONFIRMED"),
        )
    return database


def test_create_and_validate_backup_round_trip(tmp_path):
    source = tmp_path / "otimizer.db"
    backup = tmp_path / "backups" / "otimizer-001.db"
    restored = tmp_path / "restore" / "otimizer.db"
    _seed_database(source)

    assert create_backup(source, backup) == backup
    manifest = validate_backup(backup)
    assert manifest["format_version"] == 1
    assert manifest["tables"]["accounts"] == 1
    assert manifest["tables"]["licenses"] == 1
    assert manifest["tables"]["license_events"] == 1
    assert manifest["tables"]["payments"] == 1

    assert restore_backup(backup, restored) == restored
    with sqlite3.connect(source) as original, sqlite3.connect(restored) as recovered:
        for table in ("accounts", "sessions", "licenses", "license_events", "payments"):
            assert original.execute(f"SELECT COUNT(*) FROM {table}").fetchone() == recovered.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        assert original.execute("SELECT account_id,email,role FROM accounts").fetchall() == recovered.execute("SELECT account_id,email,role FROM accounts").fetchall()
        assert original.execute("SELECT license_id,license_key,status,plan FROM licenses").fetchall() == recovered.execute("SELECT license_id,license_key,status,plan FROM licenses").fetchall()
        assert original.execute("SELECT payment_id,amount_cents,status FROM payments").fetchall() == recovered.execute("SELECT payment_id,amount_cents,status FROM payments").fetchall()


def test_tampered_backup_is_rejected(tmp_path):
    source = tmp_path / "source.db"
    backup = tmp_path / "backup.db"
    _seed_database(source)
    create_backup(source, backup)
    backup.write_bytes(backup.read_bytes() + b"tampered")

    with pytest.raises(BackupError, match="SHA-256"):
        validate_backup(backup)


def test_missing_manifest_is_rejected(tmp_path):
    source = tmp_path / "source.db"
    backup = tmp_path / "backup.db"
    _seed_database(source)
    create_backup(source, backup)
    backup.with_suffix(backup.suffix + ".json").unlink()

    with pytest.raises(BackupError, match="manifest"):
        validate_backup(backup)


def test_restore_rejects_invalid_backup_without_replacing_target(tmp_path):
    source = tmp_path / "source.db"
    backup = tmp_path / "backup.db"
    target = tmp_path / "target.db"
    _seed_database(source)
    create_backup(source, backup)
    target.write_bytes(b"existing-target")
    manifest_path = backup.with_suffix(backup.suffix + ".json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(BackupError):
        restore_backup(backup, target)
    assert target.read_bytes() == b"existing-target"


def test_backup_destination_cannot_be_source(tmp_path):
    source = tmp_path / "source.db"
    _seed_database(source)
    with pytest.raises(BackupError, match="differ"):
        create_backup(source, source)


def test_prune_keeps_newest_valid_backups_and_never_deletes_invalid(tmp_path):
    source = tmp_path / "source.db"
    backup_dir = tmp_path / "backups"
    invalid = backup_dir / "invalid.db"
    _seed_database(source)
    backup_dir.mkdir()
    backups = []
    for index in range(3):
        backup = backup_dir / f"otimizer-{index}.db"
        create_backup(source, backup)
        os.utime(backup, (100 + index, 100 + index))
        backups.append(backup)
    invalid.write_bytes(b"not-a-backup")

    removed = prune_backups(backup_dir, keep=2)

    assert removed == [backups[0]]
    assert not backups[0].exists()
    assert backups[1].exists() and backups[2].exists()
    assert invalid.exists()
    assert validate_backup(backups[1])["format_version"] == 1
