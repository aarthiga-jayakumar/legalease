# LegalEase

Plain-English contract analysis. Upload a contract PDF or paste its text, optionally ask a question, and get a one-page report: summary, key clauses, risks, a direct answer and a recommendation.

**Live demo:** https://legalease-se6e.onrender.com/ (free tier, the first load can take a minute to wake up)

## How it works

1. Text is extracted from the PDF (`pdfplumber`) or taken from the text box, then cleaned.
2. A guardrail rejects empty or very short input, so the model is never asked to summarise nothing.
3. A structured prompt asks the LLM (openai/gpt-oss-120b via the Groq API) for a fixed one-page format, answering only from the document.
4. The result is shown in a Streamlit UI.

The first prototype used the Gemini API in Google AI Studio. The deployed version first used Llama 3.3 through Groq; Groq retired that model on August 16, 2026, so it now runs openai/gpt-oss-120b, set through the GROQ_MODEL environment variable.



## Project layout

|Path|Purpose|
|-|-|
|`app.py`|Streamlit UI|
|`core.py`|Text cleaning, PDF extraction, validation, prompt building, LLM call|
|`tests/test_core.py`|Unit tests (LLM mocked, no API key needed)|
|`src/`|Experimental multi-agent pipeline (orchestrator, classifier, drafter, validator, memory)|

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

* Not legal advice. Output is an AI summary and can be wrong, so check important clauses yourself.
* Very long contracts may exceed the model's context window; there is no chunking yet.
* Scanned PDFs without a text layer are not supported (no OCR).

