# src/utils/prompts.py
# Centralized prompt templates for LLMs. Tweak for quality.

CLASSIFY_PROMPT = """You are a legal issue classifier. Given a user's plain English description, return a JSON object with:
- category: one of ["landlord_tenant","employment","consumer","contract","family","other"]
- tags: short list of relevant tags (comma separated)
- short_summary: a 1-2 sentence summary in plain English.

User description:
\"\"\"{text}\"\"\"
"""

DRAFT_PROMPT = """You are a professional legal assistant that drafts concise, plain-English demand letters and templates.
Inputs:
- category: {category}
- jurisdiction: {jurisdiction}
- facts: {facts}
- user_goal: {goal}

Produce:
1) a short 1-paragraph "purpose" summary.
2) a draft letter (include placeholders like [NAME], [DATE], [ADDRESS]).
3) a short "next steps" checklist (3 items).
Return all parts separated by the marker "===SECTION===".
"""

VALIDATOR_PROMPT = """You are a template quality checker. Given a draft letter and the facts, return JSON with:
- ok: true/false
- missing_facts: list of missing items (if any)
- suggestions: brief suggestions to improve clarity/legality (2 items)

Draft:
\"\"\"{draft}\"\"\"

Facts:
\"\"\"{facts}\"\"\"
"""
