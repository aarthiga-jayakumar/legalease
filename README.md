# LegalEase

Plain-English contract analysis. Upload a contract PDF or paste its text, optionally ask a question, and get a one-page report: summary, key clauses, risks, a direct answer and a recommendation.

**Live demo:** https://legalease-se6e.onrender.com/ (free tier, the first load can take a minute to wake up)

## How it works

1. Text is extracted from the PDF (`pdfplumber`) or taken from the text box, then cleaned.
2. A guardrail rejects empty or very short input, so the model is never asked to summarise nothing.
3. A structured prompt asks the LLM (Llama 3.3 70B via the Groq API) for a fixed one-page format, answering only from the document.
4. The result is shown in a Streamlit UI.

The first prototype used the Gemini API in Google AI Studio. The deployed version uses Llama 3.3 through Groq.

## Project layout

| Path | Purpose |
|---|---|
| `app.py` | Streamlit UI |
| `core.py` | Text cleaning, PDF extraction, validation, prompt building, LLM call |
| `api.py` | FastAPI REST service (`POST /analyze`, `GET /results/{id}`, `GET /health`) |
| `storage.py` | Amazon S3 (uploaded PDFs) and Amazon DynamoDB (analysis results) |
| `scripts/setup_aws.py` | Creates the S3 bucket and DynamoDB table |
| `tests/` | Unit tests (LLM and AWS mocked, no keys or accounts needed) |
| `src/` | Experimental multi-agent pipeline (orchestrator, classifier, drafter, validator, memory) |

## REST API with S3 and DynamoDB

`POST /analyze` takes a contract PDF and an optional question. The PDF is stored in S3, the text is analysed by the LLM, and the result is saved in DynamoDB. `GET /results/{id}` returns a saved result. Uploads are limited to 10 MB and must be PDFs.

```bash
aws configure                       # use an IAM user limited to S3 and DynamoDB, region ap-south-1
python scripts/setup_aws.py         # creates the bucket (public access blocked) and table, prints the exports
export LEGALEASE_BUCKET=...         # values printed by the script
export LEGALEASE_TABLE=legalease-results
export AWS_REGION=ap-south-1
export GROQ_API_KEY=your_key_here
uvicorn api:app --reload            # interactive docs at http://127.0.0.1:8000/docs
```

## Run locally

```bash
pip install -r requirements.txt
export GROQ_API_KEY=your_key_here      # never commit this
streamlit run app.py
```

## Run the tests

```bash
pip install -r requirements-dev.txt
pytest
```

## Known limitations

- Not legal advice. Output is an AI summary and can be wrong, so check important clauses yourself.
- Very long contracts may exceed the model's context window; there is no chunking yet.
- Scanned PDFs without a text layer are not supported (no OCR).
