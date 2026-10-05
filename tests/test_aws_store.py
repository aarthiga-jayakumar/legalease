"""Tests for AwsStore (S3 + DynamoDB). AWS is mocked with moto, so no account or keys are needed."""
import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

import api
import core
from storage import AwsStore, SQLiteStore

BUCKET = "test-legalease-bucket"
TABLE = "legalease-results"
REGION = "ap-south-1"
PDF = b"%PDF-1.4 fake pdf bytes"


@pytest.fixture(autouse=True)
def fake_aws_env(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", REGION)
    monkeypatch.setenv("AWS_REGION", REGION)
    monkeypatch.setenv("LEGALEASE_TABLE", TABLE)


@pytest.fixture
def aws():
    with mock_aws():
        boto3.client("s3", region_name=REGION).create_bucket(
            Bucket=BUCKET, CreateBucketConfiguration={"LocationConstraint": REGION}
        )
        boto3.client("dynamodb", region_name=REGION).create_table(
            TableName=TABLE,
            AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
            KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield


@pytest.fixture
def store(aws):
    return AwsStore(bucket=BUCKET, table_name=TABLE, region=REGION)


def test_requires_bucket():
    with pytest.raises(RuntimeError):
        AwsStore(bucket="")


def test_round_trip_stores_pdf_in_s3_and_result_in_dynamodb(store):
    saved = store.save({"filename": "a.pdf", "question": "Who pays?", "report": "r"}, pdf=PDF)
    assert saved["id"] and saved["created_at"]
    assert saved["s3_key"] == f"uploads/{saved['id']}.pdf"

    obj = boto3.client("s3", region_name=REGION).get_object(Bucket=BUCKET, Key=saved["s3_key"])
    assert obj["Body"].read() == PDF
    assert store.get(saved["id"]) == saved


def test_none_question_is_stored(store):
    saved = store.save({"filename": "a.pdf", "question": None, "report": "r"}, pdf=PDF)
    assert store.get(saved["id"])["question"] is None


def test_save_without_pdf_skips_s3(store):
    saved = store.save({"filename": "a.pdf", "report": "r"})
    assert "s3_key" not in saved
    assert boto3.client("s3", region_name=REGION).list_objects_v2(Bucket=BUCKET).get("KeyCount", 0) == 0


def test_unknown_id_returns_none(store):
    assert store.get("nope") is None


def test_sqlite_store_accepts_pdf_argument(tmp_path):
    sqlite = SQLiteStore(str(tmp_path / "t.db"))
    saved = sqlite.save({"filename": "a.pdf", "report": "r"}, pdf=PDF)
    assert sqlite.get(saved["id"]) == saved


def test_get_store_uses_aws_when_bucket_is_set(aws, monkeypatch):
    monkeypatch.setattr(api, "_store", None)
    monkeypatch.setenv("LEGALEASE_BUCKET", BUCKET)
    assert isinstance(api.get_store(), AwsStore)


def test_get_store_uses_sqlite_without_bucket(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "_store", None)
    monkeypatch.delenv("LEGALEASE_BUCKET", raising=False)
    monkeypatch.setenv("LEGALEASE_DB", str(tmp_path / "t.db"))
    assert isinstance(api.get_store(), SQLiteStore)


def test_api_end_to_end_with_aws_store(store, monkeypatch):
    api.app.dependency_overrides[api.get_store] = lambda: store
    monkeypatch.setattr(core, "extract_text_from_pdf_bytes", lambda data: "contract text " * 20)
    monkeypatch.setattr(core, "analyze", lambda text, question=None, client=None: "mocked report")
    try:
        client = TestClient(api.app)
        resp = client.post(
            "/analyze",
            files={"file": ("contract.pdf", PDF, "application/pdf")},
            data={"question": "What is the fee?"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["report"] == "mocked report"

        s3_key = f"uploads/{body['id']}.pdf"
        obj = boto3.client("s3", region_name=REGION).get_object(Bucket=BUCKET, Key=s3_key)
        assert obj["Body"].read() == PDF

        fetched = client.get(f"/results/{body['id']}")
        assert fetched.status_code == 200
        assert fetched.json()["question"] == "What is the fee?"
    finally:
        api.app.dependency_overrides.clear()
