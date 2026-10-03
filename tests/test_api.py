import pytest
from fastapi.testclient import TestClient

import api
import core
from storage import SQLiteStore


@pytest.fixture
def store(tmp_path):
    return SQLiteStore(str(tmp_path / "test.db"))


@pytest.fixture
def client(store, monkeypatch):
    api.app.dependency_overrides[api.get_store] = lambda: store
    monkeypatch.setattr(core, "extract_text_from_pdf_bytes", lambda data: "contract text " * 20)
    monkeypatch.setattr(core, "analyze", lambda text, question=None, client=None: "mocked report")
    yield TestClient(api.app)
    api.app.dependency_overrides.clear()


def pdf(name="contract.pdf", data=b"%PDF-1.4 fake"):
    return {"file": (name, data, "application/pdf")}


# ---- storage ----

def test_store_round_trip(store):
    saved = store.save({"filename": "a.pdf", "report": "r"})
    assert saved["id"] and saved["created_at"]
    assert store.get(saved["id"]) == saved


def test_store_unknown_id_returns_none(store):
    assert store.get("does-not-exist") is None


# ---- API ----

def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_analyze_returns_report_and_saves_it(client, store):
    resp = client.post("/analyze", files=pdf(), data={"question": "What is the fee?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["report"] == "mocked report"
    assert body["filename"] == "contract.pdf"
    assert body["question"] == "What is the fee?"
    assert store.get(body["id"])["report"] == "mocked report"


def test_get_result_returns_saved_result(client):
    created = client.post("/analyze", files=pdf()).json()
    resp = client.get(f"/results/{created['id']}")
    assert resp.status_code == 200
    assert resp.json() == created


def test_get_unknown_result_is_404(client):
    assert client.get("/results/nope").status_code == 404


def test_non_pdf_is_rejected(client):
    resp = client.post("/analyze", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert resp.status_code == 415


def test_empty_file_is_rejected(client):
    assert client.post("/analyze", files=pdf(data=b"")).status_code == 400


def test_unreadable_pdf_is_422(client, monkeypatch):
    def boom(data):
        raise ValueError("bad pdf")

    monkeypatch.setattr(core, "extract_text_from_pdf_bytes", boom)
    assert client.post("/analyze", files=pdf()).status_code == 422


def test_too_short_document_is_422(client, monkeypatch):
    def too_short(text, question=None, client=None):
        raise core.InvalidDocumentError("Document is too short to analyse.")

    monkeypatch.setattr(core, "analyze", too_short)
    resp = client.post("/analyze", files=pdf())
    assert resp.status_code == 422
    assert "too short" in resp.json()["detail"]


def test_missing_api_key_is_503(client, monkeypatch):
    def no_key(text, question=None, client=None):
        raise RuntimeError("GROQ_API_KEY is not set.")

    monkeypatch.setattr(core, "analyze", no_key)
    assert client.post("/analyze", files=pdf()).status_code == 503


def test_llm_failure_is_502(client, monkeypatch):
    def fail(text, question=None, client=None):
        raise Exception("provider down")

    monkeypatch.setattr(core, "analyze", fail)
    assert client.post("/analyze", files=pdf()).status_code == 502