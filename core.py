"""Core logic for LegalEase: text cleaning, PDF extraction, validation, prompting and the LLM call.

Kept free of Streamlit so it can be unit tested and reused behind an API.
"""
import io
import os
import re

MODEL_ID = "llama-3.3-70b-versatile"
MIN_DOC_CHARS = 50  # below this we refuse to call the model (prevents made-up summaries)

SYSTEM_PROMPT = (
    "You are a smart legal assistant. You speak in simple English, "
    "give helpful and correct answers, and format cleanly using headings and bullet points. "
    "Use only the provided document. If it does not contain the information, say so."
)

DEFAULT_QUESTION = "Give me a useful overview based on this document."


class InvalidDocumentError(ValueError):
    """Raised when the document text is empty or too short to analyse."""


def clean_text(raw):
    """Normalise whitespace and line breaks in extracted text."""
    if not raw:
        return ""
    raw = raw.replace("\r", "")
    raw = re.sub(r"\n{2,}", "\n\n", raw)
    raw = re.sub(r" {2,}", " ", raw)
    return "\n".join(ln.strip() for ln in raw.splitlines()).strip()


def extract_text_from_pdf_bytes(data):
    """Extract and clean text from the raw bytes of a PDF."""
    import pdfplumber  # imported lazily so tests of other functions need no PDF libs

    with pdfplumber.open(io.BytesIO(data)) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]
    return clean_text("\n".join(pages))


def validate_document(text):
    """Return cleaned text, or raise InvalidDocumentError if there is not enough to analyse."""
    doc = (text or "").strip()
    if len(doc) < MIN_DOC_CHARS:
        raise InvalidDocumentError(
            f"Document is too short to analyse (need at least {MIN_DOC_CHARS} characters)."
        )
    return doc


def build_prompt(doc, question=None):
    """Build the one-page report prompt for a document and an optional question."""
    question = (question or "").strip() or DEFAULT_QUESTION
    return f"""
You MUST produce a **one-page clean report**.

STYLE RULES:
- Use **clear headings** (bold allowed)
- Use short bullet points (8-18 words)
- No paragraphs
- No repeated ideas
- Simple English everyone can understand
- Highlight key terms using **bold** only
- Output must not exceed one page visually

FORMAT EXACTLY:

📘 **Summary (3 bullets)**
- ...

📌 **Key Clauses (4 bullets)**
- ...

⚠️ **Risks (3 bullets)**
- ...

💬 **Answer to Your Question**
1-2 sentence answer in **simple English**, based only on the document.

✔️ **Recommendation (max 2 lines)**
Short and practical suggestion.

---------------------------------

DOCUMENT:
{doc}

QUESTION:
{question}
"""


def get_client():
    """Create the Groq client lazily so importing this module never needs an API key."""
    from groq import Groq

    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise RuntimeError("GROQ_API_KEY is not set.")
    return Groq(api_key=key)


def call_model(prompt, max_tokens=700, client=None):
    """Send the prompt to the LLM and return the text answer. A client can be injected for tests."""
    client = client or get_client()
    resp = client.chat.completions.create(
        model=MODEL_ID,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content.strip()


def analyze(text, question=None, client=None):
    """Validate the document, build the prompt and return the model's report."""
    doc = validate_document(text)
    return call_model(build_prompt(doc, question), client=client)
