# src/agents/template_drafter.py
from ..utils.prompts import DRAFT_PROMPT
from ..utils.logger import logger

def draft_template(category: str, jurisdiction: str, facts: str, goal: str, call_llm):
    prompt = DRAFT_PROMPT.format(category=category, jurisdiction=jurisdiction, facts=facts, goal=goal)
    logger.info("Calling LLM to draft template...")
    raw = call_llm(prompt, max_tokens=800)
    # We expect sections separated by ===SECTION===
    if "===SECTION===" in raw:
        parts = raw.split("===SECTION===")
        return {"purpose": parts[0].strip(), "letter": parts[1].strip() if len(parts) > 1 else "", "next_steps": parts[2].strip() if len(parts) > 2 else ""}
    # fallback: return full raw as letter
    return {"purpose": "", "letter": raw.strip(), "next_steps": ""}
