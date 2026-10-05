"""Result storage for the LegalEase API.

Two stores share the same interface, save(record, pdf=None) and get(id):
  SQLiteStore  keeps results in a local file (default, no setup).
  AwsStore     keeps the uploaded PDF in Amazon S3 and the result in Amazon DynamoDB.
               Used automatically when the LEGALEASE_BUCKET environment variable is set.

AwsStore settings (environment variables):
  LEGALEASE_BUCKET  S3 bucket name
  LEGALEASE_TABLE   DynamoDB table name (default: legalease-results)
  AWS_REGION        region (default: ap-south-1)
Credentials come from the standard AWS chain (aws configure, env vars or an EC2 IAM role).
"""
import json
import os
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

    def save(self, record, pdf=None):
        """Store a result. Adds an id and created_at if they are missing. Returns the saved record.

        The pdf argument is accepted so both stores share one interface; SQLiteStore ignores it.
        """
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


class AwsStore:
    """Uploaded PDFs go to S3 (uploads/<id>.pdf); results go to a DynamoDB table keyed by id."""

    def __init__(self, bucket, table_name="legalease-results", region="ap-south-1", s3=None, dynamodb=None):
        if not bucket:
            raise RuntimeError("LEGALEASE_BUCKET is not set.")
        import boto3  # imported here so SQLite-only installs do not need boto3

        self.bucket = bucket
        self.s3 = s3 or boto3.client("s3", region_name=region)
        self.table = (dynamodb or boto3.resource("dynamodb", region_name=region)).Table(table_name)

    @classmethod
    def from_env(cls):
        return cls(
            bucket=os.environ.get("LEGALEASE_BUCKET"),
            table_name=os.environ.get("LEGALEASE_TABLE", "legalease-results"),
            region=os.environ.get("AWS_REGION", "ap-south-1"),
        )

    def save(self, record, pdf=None):
        """Store the PDF in S3 (if given) and the result in DynamoDB. Returns the saved record."""
        record = dict(record)
        record.setdefault("id", uuid.uuid4().hex)
        record.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        if pdf is not None:
            key = f"uploads/{record['id']}.pdf"
            self.s3.put_object(Bucket=self.bucket, Key=key, Body=pdf, ContentType="application/pdf")
            record["s3_key"] = key
        self.table.put_item(Item=record)
        return record

    def get(self, result_id):
        """Return the stored record for an id, or None if it does not exist."""
        return self.table.get_item(Key={"id": result_id}).get("Item")
