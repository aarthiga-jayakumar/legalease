"""LegalEase REST API.

POST /analyze      upload a contract PDF (+ optional question) -> stored in S3, analysed, result stored in DynamoDB
GET  /results/{id} fetch a saved result
GET  /health       liveness check

Run locally:  uvicorn api:app --reload      (interactive docs at /docs)
"""
import uuid

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile

from core import InvalidDocumentError, analyze, extract_text_from_pdf_bytes
from storage import Storage

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB

app = FastAPI(title="LegalEase API", version="1.0")


def get_storage():
    """Dependency so tests can swap in a mocked-AWS Storage."""
    try:
        return Storage.from_env()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/analyze")
async def analyze_contract(
    file: UploadFile = File(...),
    question: str = Form(""),
    storage: Storage = Depends(get_storage),
):
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File is larger than 10 MB.")
    if not data.startswith(b"%PDF"):
        raise HTTPException(status_code=415, detail="Only PDF files are supported.")

    try:
        text = extract_text_from_pdf_bytes(data)
    except Exception:
        raise HTTPException(status_code=422, detail="Could not read this PDF.")

    try:
        report = analyze(text, question)
    except InvalidDocumentError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    doc_id = uuid.uuid4().hex
    s3_key = storage.save_upload(doc_id, data)
    storage.save_result(doc_id, file.filename or "upload.pdf", question, report, s3_key)
    return {"id": doc_id, "report": report}


@app.get("/results/{doc_id}")
def get_result(doc_id: str, storage: Storage = Depends(get_storage)):
    item = storage.get_result(doc_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Result not found.")
    return item
