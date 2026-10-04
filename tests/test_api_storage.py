"""Tests for the S3/DynamoDB storage layer and the REST API.

AWS is mocked with moto and the LLM is mocked, so these run offline with no accounts or keys.
"""
import io

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

import api
import storage

BUCKET = "test-legalease-bucket"
TABLE = "legalease-results"
REGION = "ap-south-1"

CONTRACT_TEXT = "Payment is due within 30 days. Either party may terminate with 15 days notice. Late fees apply."


@pytest.fixture(autouse=True)
def fake_aws_credentials(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", REGION)
    monkeypatch.setenv("AWS_REGION", REGION)
    monkeypatch.setenv("LEGALEASE_BUCKET", BUCKET)
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
def client(aws, monkeypatch):
    monkeypatch.setattr(api, "analyze", lambda text, question=None, client=None: f"REPORT for: {text[:20]}")
    monkeypatch.setattr(api, "extract_text_from_pdf_bytes", lambda data: CONTRACT_TEXT)
    return TestClient(api.app)


PDF_BYTES = b"%PDF-1.4 fake pdf bytes for testing"


def upload(client, data=PDF_BYTES, name="contract.pdf", question=""):
    return client.post("/analyze", files={"file": (name, io.BytesIO(data), "application/pdf")}, data={"question": question})


# ---------- Storage ----------
def test_storage_requires_bucket():
    with pytest.raises(RuntimeError):
        storage.Storage(bucket="")


def test_upload_and_result_roundtrip(aws):
    store = storage.Storage.from_env()
    key = store.save_upload("abc123", PDF_BYTES)
    assert key == "uploads/abc123.pdf"

    obj = boto3.client("s3", region_name=REGION).get_object(Bucket=BUCKET, Key=key)
    assert obj["Body"].read() == PDF_BYTES

    store.save_result("abc123", "c.pdf", "When due?", "the report", key)
    item = store.get_result("abc123")
    assert item["report"] == "the report"
    assert item["question"] == "When due?"
    assert item["s3_key"] == key
    assert "created_at" in item


def test_get_result_missing_returns_none(aws):
    assert storage.Storage.from_env().get_result("nope") is None


# ---------- API ----------
def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_analyze_stores_pdf_and_result_then_fetches_it(client):
    resp = upload(client, question="Who pays?")
    assert resp.status_code == 200
    body = resp.json()
    assert body["report"].startswith("REPORT for:")

    doc_id = body["id"]
    s3_obj = boto3.client("s3", region_name=REGION).get_object(Bucket=BUCKET, Key=f"uploads/{doc_id}.pdf")
    assert s3_obj["Body"].read() == PDF_BYTES

    got = client.get(f"/results/{doc_id}")
    assert got.status_code == 200
    assert got.json()["report"] == body["report"]
    assert got.json()["question"] == "Who pays?"
    assert got.json()["filename"] == "contract.pdf"


def test_get_unknown_result_is_404(client):
    assert client.get("/results/unknown").status_code == 404


def test_rejects_empty_file(client):
    assert upload(client, data=b"").status_code == 400


def test_rejects_non_pdf(client):
    assert upload(client, data=b"just some text, not a pdf", name="a.txt").status_code == 415


def test_rejects_oversized_file(client, monkeypatch):
    monkeypatch.setattr(api, "MAX_UPLOAD_BYTES", 10)
    assert upload(client).status_code == 413


def test_too_short_document_returns_422_and_stores_nothing(aws, monkeypatch):
    from core import InvalidDocumentError

    def raise_invalid(text, question=None, client=None):
        raise InvalidDocumentError("too short")

    monkeypatch.setattr(api, "analyze", raise_invalid)
    monkeypatch.setattr(api, "extract_text_from_pdf_bytes", lambda data: "hi")
    resp = upload(TestClient(api.app))
    assert resp.status_code == 422

    listing = boto3.client("s3", region_name=REGION).list_objects_v2(Bucket=BUCKET)
    assert listing.get("KeyCount", 0) == 0


def test_missing_bucket_config_returns_500(aws, monkeypatch):
    monkeypatch.delenv("LEGALEASE_BUCKET")
    monkeypatch.setattr(api, "analyze", lambda *a, **k: "x")
    monkeypatch.setattr(api, "extract_text_from_pdf_bytes", lambda data: CONTRACT_TEXT)
    assert upload(TestClient(api.app)).status_code == 500
