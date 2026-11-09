"""Consistent SQLite backups with verification and optional S3 storage.

The service never copies the live SQLite file directly.  It uses SQLite's
online backup API, so WAL contents are included in a consistent snapshot.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from db_improved import DB_PATH
from services.logging_config import get_logger

log = get_logger("backup")


def _backup_dir() -> Path:
    return Path(os.getenv("BACKUP_DIR", Path(__file__).resolve().parent / "backups"))


def _integrity_check(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        result = conn.execute("PRAGMA integrity_check").fetchone()
        if not result or result[0] != "ok":
            raise RuntimeError(f"SQLite integrity_check failed: {result!r}")
        conn.execute("SELECT name FROM sqlite_master LIMIT 1").fetchone()
    finally:
        conn.close()


def _encrypt(source: Path, target: Path) -> None:
    key = os.getenv("BACKUP_ENCRYPTION_KEY")
    if not key:
        shutil.copy2(source, target)
        return
    try:
        from cryptography.fernet import Fernet
        target.write_bytes(Fernet(key.encode("ascii")).encrypt(source.read_bytes()))
    except ImportError as exc:
        raise RuntimeError("BACKUP_ENCRYPTION_KEY is set but cryptography is not installed") from exc


def _upload_s3(path: Path, key: str) -> None:
    bucket = os.getenv("BACKUP_S3_BUCKET")
    if not bucket:
        return
    try:
        import boto3
        client = boto3.client(
            "s3",
            endpoint_url=os.getenv("BACKUP_S3_ENDPOINT") or None,
            region_name=os.getenv("BACKUP_S3_REGION") or None,
        )
        client.upload_file(str(path), bucket, key, ExtraArgs={"ServerSideEncryption": "AES256"})
    except ImportError as exc:
        raise RuntimeError("BACKUP_S3_BUCKET is set but boto3 is not installed") from exc


def _prune_s3(days: int = 30) -> None:
    bucket = os.getenv("BACKUP_S3_BUCKET")
    if not bucket:
        return
    try:
        import boto3
        client = boto3.client(
            "s3",
            endpoint_url=os.getenv("BACKUP_S3_ENDPOINT") or None,
            region_name=os.getenv("BACKUP_S3_REGION") or None,
        )
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        paginator = client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=bucket, Prefix="sportbot/"):
            for item in page.get("Contents", []):
                if item["LastModified"] < cutoff:
                    client.delete_object(Bucket=bucket, Key=item["Key"])
    except ImportError as exc:
        raise RuntimeError("BACKUP_S3_BUCKET is set but boto3 is not installed") from exc


def _prune_old(directory: Path, days: int = 30) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    for path in directory.glob("sportbot-*.sqlite3*"):
        if datetime.fromtimestamp(path.stat().st_mtime, timezone.utc) < cutoff:
            path.unlink()
    for path in directory.glob("*.json"):
        if datetime.fromtimestamp(path.stat().st_mtime, timezone.utc) < cutoff:
            path.unlink()


def create_backup(source: str | Path = DB_PATH, directory: str | Path | None = None) -> dict:
    """Create, verify, hash, optionally encrypt, and optionally upload a backup."""
    source = Path(source)
    directory = Path(directory) if directory else _backup_dir()
    directory.mkdir(parents=True, exist_ok=True)
    if not source.exists() or source.stat().st_size == 0:
        raise FileNotFoundError(f"SQLite database is missing or empty: {source}")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    plain = directory / f"sportbot-{stamp}-{os.getpid()}.sqlite3"
    final = plain.with_suffix(plain.suffix + ".enc") if os.getenv("BACKUP_ENCRYPTION_KEY") else plain
    manifest_path = directory / f"{plain.stem}.json"

    with tempfile.NamedTemporaryFile(prefix="sportbot-backup-", suffix=".sqlite3", dir=directory, delete=False) as tmp:
        temp_path = Path(tmp.name)
    try:
        source_conn = sqlite3.connect(source, uri=False)
        target_conn = sqlite3.connect(temp_path)
        try:
            source_conn.backup(target_conn, pages=100, sleep=0.05)
            target_conn.commit()
        finally:
            target_conn.close()
            source_conn.close()
        _integrity_check(temp_path)
        _encrypt(temp_path, final)
    finally:
        temp_path.unlink(missing_ok=True)

    digest = hashlib.sha256(final.read_bytes()).hexdigest()
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "file": final.name,
        "sha256": digest,
        "size_bytes": final.stat().st_size,
        "integrity_check": "ok",
        "encrypted": final.suffix == ".enc",
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    _upload_s3(final, f"sportbot/{final.name}")
    _upload_s3(manifest_path, f"sportbot/{manifest_path.name}")
    _prune_s3()
    _prune_old(directory)
    log.info("Created verified database backup %s (%d bytes)", final, manifest["size_bytes"])
    return manifest


if __name__ == "__main__":
    print(json.dumps(create_backup(), indent=2))
