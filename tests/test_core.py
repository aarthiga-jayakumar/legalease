"""Unit tests for LegalEase core logic. The LLM is mocked, so these run offline with no API key."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import core

LONG_DOC = (
    "This Service Agreement is made between Acme Ltd and the Client. "
    "Payment is due within 30 days. Either party may terminate with 15 days notice."
)


def fake_client(reply="  mocked report  "):
    """Build a stand-in for the Groq client that returns a fixed reply."""
    client = MagicMock()
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=reply))]
    )
    return client


# ---------- clean_text ----------
def test_clean_text_empty_and_none():
    assert core.clean_text("") == ""
    assert core.clean_text(None) == ""


def test_clean_text_collapses_spaces_and_blank_lines():
    raw = "Clause  1:   Payment\r\n\n\n\n  Clause 2:  Term  "
    assert core.clean_text(raw) == "Clause 1: Payment\n\nClause 2: Term"


# ---------- validate_document (the hallucination guardrail) ----------
@pytest.mark.parametrize("bad", [None, "", "   ", "too short"])
def test_validate_rejects_empty_or_short(bad):
    with pytest.raises(core.InvalidDocumentError):
        core.validate_document(bad)


def test_validate_accepts_and_strips():
    assert core.validate_document("  " + LONG_DOC + "  ") == LONG_DOC


# ---------- build_prompt ----------
def test_build_prompt_includes_document_and_question():
    prompt = core.build_prompt(LONG_DOC, "When is payment due?")
    assert LONG_DOC in prompt
    assert "When is payment due?" in prompt
    assert "Risks" in prompt


@pytest.mark.parametrize("empty_question", [None, "", "   "])
def test_build_prompt_uses_default_question(empty_question):
    assert core.DEFAULT_QUESTION in core.build_prompt(LONG_DOC, empty_question)


# ---------- call_model ----------
def test_call_model_returns_stripped_text_and_uses_model():
    client = fake_client()
    assert core.call_model("hello", client=client) == "mocked report"
    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == core.MODEL_ID
    assert kwargs["max_tokens"] == 700
    assert kwargs["messages"][0]["role"] == "system"
    assert kwargs["messages"][1] == {"role": "user", "content": "hello"}


def test_get_client_requires_api_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        core.get_client()


# ---------- analyze (end to end, mocked) ----------
def test_analyze_happy_path():
    client = fake_client("final report")
    assert core.analyze(LONG_DOC, "Who are the parties?", client=client) == "final report"
    sent = client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
    assert "Who are the parties?" in sent and LONG_DOC in sent


def test_analyze_does_not_call_model_for_empty_document():
    client = fake_client()
    with pytest.raises(core.InvalidDocumentError):
        core.analyze("", client=client)
    client.chat.completions.create.assert_not_called()


# ---------- PDF extraction ----------
def test_extract_text_from_generated_pdf():
    pytest.importorskip("pdfplumber")
    reportlab_canvas = pytest.importorskip("reportlab.pdfgen.canvas")
    import io

    buf = io.BytesIO()
    c = reportlab_canvas.Canvas(buf)
    c.drawString(72, 750, "Payment is due within 30 days.")
    c.save()

    text = core.extract_text_from_pdf_bytes(buf.getvalue())
    assert "Payment is due within 30 days." in text
