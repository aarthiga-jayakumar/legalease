# src/agents/issue_classifier.py
import os
import json
from ..utils.prompts import CLASSIFY_PROMPT
from ..utils.logger import logger

# Try to import OpenAI, but provide a mock fallback for offline testing.
try:
    import openai
    OPENAI_AVAILABLE = True
except Exception:
    OPENAI_AVAILABLE = False

def call_llm(prompt: str, max_tokens: int = 300):
    if OPENAI_AVAILABLE and os.getenv("OPENAI_API_KEY"):
        resp = openai.ChatCompletion.create(
            model="gpt-4o-mini" if False else "gpt-4o-mini", # Replace with your model
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content
    # Mock fallback (useful for demo)
    logger.info("OpenAI not available — using mock classifier.")
    return json.dumps({
        "category": "landlord_tenant",
        "tags": "utility_cut, non_payment",
        "short_summary": "Tenant reports landlord cut water supply despite rent paid."
    })

def classify_issue(text: str) -> dict:
    prompt = CLASSIFY_PROMPT.format(text=text)
    raw = call_llm(prompt)
    # Try parse JSON; fallback to heuristic
    try:
        import json
        parsed = json.loads(raw)
        return parsed
    except Exception:
        logger.info("LLM did not return strict JSON, using heuristics.")
        return {"category": "other", "tags": "", "short_summary": text[:200]}
