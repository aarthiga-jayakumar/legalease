# src/agents/template_validator.py
import json
from ..utils.prompts import VALIDATOR_PROMPT
from ..utils.logger import logger

def validate_with_llm(draft: str, facts: str, call_llm):
    """
    call_llm is a function that accepts a prompt and returns text.
    """
    prompt = VALIDATOR_PROMPT.format(draft=draft, facts=facts)
    resp = call_llm(prompt, max_tokens=250)
    # try JSON parse
    try:
        return json.loads(resp)
    except Exception:
        # Very small heuristic validator
        missing = []
        if "[NAME]" not in draft:
            missing.append("recipient name placeholder [NAME]")
        ok = len(missing) == 0
        return {"ok": ok, "missing_facts": missing, "suggestions": ["Add recipient name placeholder."]}
