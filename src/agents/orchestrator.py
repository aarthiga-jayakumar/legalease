# src/agents/orchestrator.py
import os
import uuid
from ..utils.logger import logger
from .issue_classifier import classify_issue, call_llm as classifier_llm_call
from .template_drafter import draft_template
from .template_validator import validate_with_llm
from ..agents.memory_agent import store_case
from ..tools.export_tool import save_markdown

# Simple LLM wrapper function that uses OpenAI if available, else a mock.
try:
    import openai
    OPENAI = True
except:
    OPENAI = False

def call_llm(prompt: str, max_tokens: int = 300):
    if OPENAI and os.getenv("OPENAI_API_KEY"):
        resp = openai.ChatCompletion.create(
            model="gpt-4o-mini" if False else "gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content
    # fallback mock
    logger.info("LLM key not found — returning mock response.")
    # Very simple mock: repeat prompt brief
    return "===SECTION===\nPurpose: This is a mock purpose.\n===SECTION===\n[NAME]\nDear [NAME],\n\nThis is a mock demand letter.\n\nSincerely,\n[YOUR NAME]\n===SECTION===\n1) Send letter\n2) Wait 14 days\n3) Contact legal aid"

def handle_text_case(user_text: str, jurisdiction: str = "Unknown", user_goal: str = "Request compliance"):
    # 1. Classify
    cls = classify_issue(user_text)
    category = cls.get("category", "other")
    facts = cls.get("short_summary", user_text)
    # 2. Draft
    draft = draft_template(category, jurisdiction, facts, user_goal, call_llm)
    # 3. Validate (loop once or twice)
    validation = validate_with_llm(draft.get("letter",""), facts, call_llm)
    retries = 0
    while (not validation.get("ok", False)) and retries < 2:
        # For simplicity, if missing facts, include a placeholder addition and retry
        logger.info("Validation failed. Missing: " + str(validation.get("missing_facts")))
        facts = facts + " " + " ".join(["[MISSING_INFO_PLACEHOLDER]"])
        draft = draft_template(category, jurisdiction, facts, user_goal, call_llm)
        validation = validate_with_llm(draft.get("letter",""), facts, call_llm)
        retries += 1
    # 4. Store in memory
    case_id = str(uuid.uuid4())[:8]
    case_obj = {"case_id": case_id, "category": category, "facts": facts, "draft": draft, "status": "drafted"}
    store_case(case_obj)
    # 5. Export draft to markdown file
    md = f"# Case {case_id}\n\n**Category:** {category}\n\n**Facts:**\n{facts}\n\n**Purpose:**\n{draft.get('purpose')}\n\n**Letter:**\n{draft.get('letter')}\n\n**Next steps:**\n{draft.get('next_steps')}\n"
    out = save_markdown(md, os.path.join(os.getcwd(), "outputs"), f"case_{case_id}.md")
    return {"case_id": case_id, "markdown": out, "validation": validation, "draft": draft}
