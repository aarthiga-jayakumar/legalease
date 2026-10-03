"""LegalEase REST API.

POST /analyze          upload a PDF (and an optional question) -> analysis report + result id
GET  /results/{id}     read a saved result back
GET  /health           simple liveness check

Run locally:  uvicorn api:app --reload      then open http://127.0.0.1:8000/docs
"""
import os

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

import core
from storage import SQLiteStore

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB

app = FastAPI(title="LegalEase API", version="0.1.0")

_store = None


def get_store():
    """Create the store on first use. Tests replace this with a temporary store."""
    global _store
    if _store is None:
        _store = SQLiteStore(os.environ.get("LEGALEASE_DB", "legalease_results.db"))
    return _store


class ResultOut(BaseModel):
    id: str
    filename: str
    question: str | None = None
    report: str
    created_at: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/analyze", response_model=ResultOut)
def analyze_pdf(
    file: UploadFile = File(...),
    question: str | None = Form(None),
    store=Depends(get_store),
):
    filename = file.filename or "upload.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Only PDF files are supported.")

    data = file.file.read()
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File is too large (limit 10 MB).")

    try:
        text = core.extract_text_from_pdf_bytes(data)
    except Exception:
        raise HTTPException(status_code=422, detail="Could not read text from this PDF.")

    try:
        report = core.analyze(text, question or None)
    except core.InvalidDocumentError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except RuntimeError as exc:  # for example GROQ_API_KEY is not set
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=502, detail="The analysis service failed. Please try again.")

    return store.save({"filename": filename, "question": question or None, "report": report})


@app.get("/results/{result_id}", response_model=ResultOut)
def get_result(result_id: str, store=Depends(get_store)):
    record = store.get(result_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Result not found.")
    return record
