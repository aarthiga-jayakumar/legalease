"""Result storage for the LegalEase API.

SQLiteStore keeps results in a local file. It exposes save() and get(), so it can be
replaced by an S3 + DynamoDB store later without changing api.py.
"""
import json
import sqlite3
import uuid
from datetime import datetime, timezone


class SQLiteStore:
    def __init__(self, path="legalease_results.db"):
        self.path = path
        self._run("CREATE TABLE IF NOT EXISTS results (id TEXT PRIMARY KEY, data TEXT NOT NULL)")

    def _run(self, sql, params=()):
        conn = sqlite3.connect(self.path)
        try:
            with conn:  # commits on success, rolls back on error
                return conn.execute(sql, params).fetchall()
        finally:
            conn.close()

    def save(self, record):
        """Store a result. Adds an id and created_at if they are missing. Returns the saved record."""
        record = dict(record)
        record.setdefault("id", uuid.uuid4().hex)
        record.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        self._run(
            "INSERT OR REPLACE INTO results (id, data) VALUES (?, ?)",
            (record["id"], json.dumps(record)),
        )
        return record

    def get(self, result_id):
        """Return the stored record for an id, or None if it does not exist."""
        rows = self._run("SELECT data FROM results WHERE id = ?", (result_id,))
        return json.loads(rows[0][0]) if rows else None
