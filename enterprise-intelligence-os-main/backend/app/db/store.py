from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any


def _database_path() -> str:
    configured = os.getenv("EIOS_DB_PATH")
    if configured:
        return configured
    path = Path(__file__).resolve().parents[2] / "data" / "enterprise-intelligence.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(_database_path())
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize() -> None:
    with _connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS datasets (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                dataset_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(dataset_id) REFERENCES datasets(id)
            );
            CREATE TABLE IF NOT EXISTS questions (
                id TEXT PRIMARY KEY,
                dataset_id TEXT NOT NULL,
                fingerprint TEXT NOT NULL UNIQUE,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(dataset_id) REFERENCES datasets(id)
            );
            """
        )
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(tasks)")}
        if "idempotency_key" not in columns:
            connection.execute("ALTER TABLE tasks ADD COLUMN idempotency_key TEXT")
        connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_idempotency_key "
            "ON tasks(idempotency_key) WHERE idempotency_key IS NOT NULL"
        )


def _with_dataset_quality(payload: dict[str, Any]) -> dict[str, Any]:
    if "quality" in payload:
        return payload
    anomalies = payload.get("anomalies") or []
    warnings = payload.get("warnings") or []
    issues = [
        {
            "type": "outlier",
            "severity": "warning",
            "message": "Suspicious revenue outlier detected",
            "columns": ["revenue"],
            "rows": [item["row"]] if isinstance(item, dict) and isinstance(item.get("row"), int) else [],
            "count": 1,
            "details": [str(item.get("reason", ""))] if isinstance(item, dict) else [],
        }
        for item in anomalies
    ]
    if warnings:
        issues.append({
            "type": "schema_problem",
            "severity": "warning",
            "message": "Legacy quality warnings require review",
            "columns": [],
            "rows": [],
            "count": len(warnings),
            "details": [str(warning) for warning in warnings],
        })
    payload["quality"] = {
        "issues": issues,
        "issue_count": len(issues),
        "rows_affected": len({row for issue in issues for row in issue["rows"]}),
        "has_blocking_issues": False,
    }
    return payload


def save_dataset(dataset_id: str, payload: dict[str, Any]) -> None:
    with _connect() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO datasets (id, name, payload) VALUES (?, ?, ?)",
            (dataset_id, str(payload["name"]), json.dumps(payload)),
        )


def get_dataset(dataset_id: str) -> dict[str, Any] | None:
    with _connect() as connection:
        row = connection.execute("SELECT payload FROM datasets WHERE id = ?", (dataset_id,)).fetchone()
    return _with_dataset_quality(json.loads(row["payload"])) if row else None


def list_datasets() -> list[dict[str, Any]]:
    with _connect() as connection:
        rows = connection.execute("SELECT payload FROM datasets ORDER BY rowid DESC").fetchall()
    return [_with_dataset_quality(json.loads(row["payload"])) for row in rows]


def get_task_by_idempotency_key(key: str) -> dict[str, Any] | None:
    with _connect() as connection:
        row = connection.execute(
            "SELECT payload FROM tasks WHERE idempotency_key = ?", (key,)
        ).fetchone()
    return json.loads(row["payload"]) if row else None


def save_task(
    task_id: str,
    dataset_id: str,
    payload: dict[str, Any],
    idempotency_key: str | None = None,
) -> bool:
    with _connect() as connection:
        cursor = connection.execute(
            "INSERT OR IGNORE INTO tasks (id, dataset_id, payload, idempotency_key) VALUES (?, ?, ?, ?)",
            (task_id, dataset_id, json.dumps(payload), idempotency_key),
        )
    return cursor.rowcount == 1


def get_task(task_id: str) -> dict[str, Any] | None:
    with _connect() as connection:
        row = connection.execute("SELECT payload FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return json.loads(row["payload"]) if row else None


def list_tasks() -> list[dict[str, Any]]:
    with _connect() as connection:
        rows = connection.execute("SELECT payload FROM tasks ORDER BY rowid DESC").fetchall()
    return [json.loads(row["payload"]) for row in rows]


def get_question_by_fingerprint(fingerprint: str) -> dict[str, Any] | None:
    with _connect() as connection:
        row = connection.execute("SELECT payload FROM questions WHERE fingerprint = ?", (fingerprint,)).fetchone()
    return json.loads(row["payload"]) if row else None


def save_question(payload: dict[str, Any], fingerprint: str) -> dict[str, Any]:
    with _connect() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO questions (id, dataset_id, fingerprint, payload) VALUES (?, ?, ?, ?)",
            (payload["id"], payload["dataset_id"], fingerprint, json.dumps(payload)),
        )
        row = connection.execute("SELECT payload FROM questions WHERE fingerprint = ?", (fingerprint,)).fetchone()
    return json.loads(row["payload"])


def list_questions() -> list[dict[str, Any]]:
    with _connect() as connection:
        rows = connection.execute("SELECT payload FROM questions ORDER BY rowid DESC").fetchall()
    return [json.loads(row["payload"]) for row in rows]
