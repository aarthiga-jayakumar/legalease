# app.py — LegalEase (compact custom)
# - Analyze: Summary(2 lines) + Clauses (<=3 bullets) + Risks (<=3 bullets) + Recommendation(1 line)
# - Ask (QA) mode: short grounded answers
# - Compare: compact A vs B with emojis and 2-3 bullets
# Notes: set GROQ_API_KEY in env (Render) or Kaggle secrets before running

import os
import io
import re
import json
import time
import streamlit as st
import pdfplumber
from html import escape

# Attempt to import groq safely
try:
    from groq import Groq
except Exception as e:
    Groq = None

# -----------------
# Config
# -----------------
MODEL_ID = os.environ.get("MODEL_ID", "llama-3.3-70b-versatile")
GROQ_KEY = os.environ.get("GROQ_API_KEY", None)

# Minimal CSS for compact single-page look
COMPACT_CSS = """
<style>
:root { --card-pad: 18px; --muted: #6b7280; --title: #0f172a; }
body { background: #ffffff; }
.header { display:flex; gap:12px; align-items:center; margin-bottom:12px;}
.card { padding: var(--card-pad); border-radius:12px; box-shadow:0 4px 18px rgba(15,23,42,0.06); margin-bottom:16px;}
.section-title { font-weight:700; color:var(--title); margin-bottom:6px; }
.muted { color:var(--muted); font-size:14px;}
.compact-bullet { margin: 4px 0; }
.small { font-size:14px; }
.controls { display:flex; gap:8px; align-items:center;}
.left-col { width:320px; min-width:260px; margin-right:20px; }
.right-col { flex:1; }
.icon-btn { padding:8px 12px; border-radius:8px; border:1px solid #eee; background:#fff; cursor:pointer;}
.result-row { margin-bottom:14px; }
.summary-line { margin:0 0 8px 0; }
.small-emoji { font-size:18px; margin-right:8px; }
</style>
"""

st.set_page_config(page_title="LegalEase — Compact", layout="wide", initial_sidebar_state="collapsed")
st.markdown(COMPACT_CSS, unsafe_allow_html=True)

# -----------------
# Helpers
# -----------------
def build_client():
    if Groq is None:
        return None, "groq package not installed"
    if not GROQ_KEY:
        return None, "GROQ_API_KEY not set"
    try:
        c = Groq(api_key=GROQ_KEY)
        return c, None
    except Exception as e:
        return None, str(e)

client, client_err = build_client()

def extract_text_from_pdf_bytes(data):
    fp = io.BytesIO(data)
    try:
        with pdfplumber.open(fp) as pdf:
            pages = [p.extract_text() or "" for p in pdf.pages]
        raw = "\n".join(pages)
        return clean_text(raw)
    except Exception as e:
        return ""

def clean_text(raw):
    if not raw:
        return ""
    text = raw.replace("\r", "")
    text = re.sub(r"\n{2,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    lines = [ln.strip() for ln in text.splitlines()]
    return "\n".join([l for l in lines if l])

def compact_split_sections(text, max_len=1500):
    # Minimal, split by headings (lines in ALL CAPS) or by every ~max_len chars
    if not text:
        return []
    lines = text.splitlines()
    sections = []
    current = []
    for ln in lines:
        if ln.strip() == "":
            continue
        # treat lines that look like headings as new section
        if ln.isupper() and len(ln.split()) < 10:
            if current:
                sections.append("\n".join(current).strip())
                current = []
            current.append(ln)
        else:
            current.append(ln)
        # force flush on length
        if sum(len(s) for s in current) > max_len:
            sections.append("\n".join(current).strip())
            current = []
    if current:
        sections.append("\n".join(current).strip())
    return sections

def call_model(prompt, max_tokens=400, system="You are a concise legal assistant. Keep answers very short and user-friendly."):
    """Call GROQ LLaMA chat completion, return plain text. defensive."""
    if client is None:
        return "LLM client not available: " + (client_err or "no client")
    try:
        resp = client.chat.completions.create(
            model=MODEL_ID,
            messages=[
                {"role":"system","content": system},
                {"role":"user","content": prompt}
            ],
            max_tokens=max_tokens,
            temperature=0.0
        )
        out = resp.choices[0].message.content.strip()
        return out
    except Exception as e:
        return f"LLM error: {str(e)}"

# Short prompt builders that constrain output
def prompt_summarize_section(text):
    p = f"""Summarize the following contract section in **two** short bullet lines (very short). Use plain simple English. If the text is incomplete say one short line that it is incomplete.

Section text:
{text}
"""
    return p

def prompt_extract_clauses(text):
    p = f"""From the text below, extract up to 3 **short** key legal clauses or important contract points as bullets (each bullet <= 16 words). If not present, say 'No clauses found'.

Text:
{text}
"""
    return p

def prompt_detect_risks(text):
    p = f"""Identify up to 3 **high-level** risks or red flags from this text. Each as one short bullet (<= 14 words). Use emoji ⚠️ at start of each bullet.
Text:
{text}
"""
    return p

def prompt_short_recommendation(text):
    p = f"""Given the section text below, produce a single short actionable recommendation (<= 20 words). Use one line only.

Text:
{text}
"""
    return p

def prompt_answer_question(question, context):
    p = f"""Answer the user's question briefly (one or two short lines). Use only facts supported by the context. If not found, answer "Not in document".

Context:
{context}

Question:
{question}
"""
    return p

def prompt_compare(A, B):
    p = f"""Compare Contract A and Contract B briefly. Output exactly:
1) Similarities: up to 3 bullets (start each with ✔️)
2) Differences: up to 3 bullets (start each with ❗)
3) Risks (A vs B): up to 3 bullets with "A:" or "B:" prefix (start with ⚠️)
4) Final recommendation (one short line, start with ✔️)

Contract A:
{A}

Contract B:
{B}
"""
    return p

# -----------------
# UI layout
# -----------------
st.markdown("<div class='header'><h1 style='margin:0'>📘 LegalEase</h1><div class='muted small' style='margin-left:8px'>Compact — Summary, Clauses, Risks, Rec</div></div>", unsafe_allow_html=True)
col1, col2 = st.columns([0.32, 0.68])

with col1:
    st.markdown("<div class='card'><div class='section-title'>Quick actions</div>", unsafe_allow_html=True)
    mode = st.radio("Mode", ["Home","Analyze","Ask (QA)","Compare"], index=1, label_visibility="collapsed")
    st.markdown("<div class='muted small'>Theme</div>", unsafe_allow_html=True)
    theme = st.radio("", ["Light","Dark"], index=0, horizontal=True)
    st.write("</div>", unsafe_allow_html=True)

with col2:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    # file upload and manual text
    uploaded = st.file_uploader("Upload a contract PDF", type=["pdf"])
    text_manual = st.text_area("Or paste text manually (short or whole contract)", height=140)
    st.markdown("</div>", unsafe_allow_html=True)

# -----------------
# Mode: Analyze
# -----------------
def run_analyze(source_text):
    if not source_text.strip():
        st.info("No content provided. Upload a PDF or paste text.")
        return

    # split into compact sections (top 3)
    sections = compact_split_sections(source_text)
    if not sections:
        st.info("Couldn't parse the document.")
        return

    # We'll analyze max first 5 sections but present top 3 only
    max_sections = min(len(sections), 5)
    present = min(3, max_sections)

    # Compact results container
    st.markdown("<div class='card'><div class='section-title'>📌 Extracted Results</div>", unsafe_allow_html=True)

    for i in range(present):
        sec = sections[i]
        heading = sec.splitlines()[0][:80] if sec.splitlines() else f"Section {i+1}"
        st.markdown(f"<div class='result-row'><div class='section-title'>🔹 Section: {escape(heading)}</div></div>", unsafe_allow_html=True)

        # Summary
        s_prompt = prompt_summarize_section(sec)
        summary = call_model(s_prompt, max_tokens=120)
        # Clauses
        c_prompt = prompt_extract_clauses(sec)
        clauses = call_model(c_prompt, max_tokens=140)
        # Risks
        r_prompt = prompt_detect_risks(sec)
        risks = call_model(r_prompt, max_tokens=140)
        # Recommendation
        rec = call_model(prompt_short_recommendation(sec), max_tokens=60)

        # Normalize output (very compact bullet formatting)
        def tidy_bullets(text):
            if not text or "No clauses found" in text:
                return "— No items found"
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            # keep first 3
            lines = lines[:3]
            bullets = "".join([f"<div class='compact-bullet'>• {escape(l)}</div>" for l in lines])
            return bullets

        clauses_html = tidy_bullets(clauses)
        risks_html = tidy_bullets(risks)
        summary_lines = [ln.strip() for ln in summary.splitlines() if ln.strip()][:2]
        summary_html = "<br/>".join([f"<div class='summary-line small'>{escape(ln)}</div>" for ln in summary_lines]) or "<div class='muted small'>No concise summary produced.</div>"

        # Render compact
        st.markdown("<div style='margin-bottom:6px'>" + summary_html + "</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='small'><strong>Clauses:</strong>{clauses_html}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='small'><strong>Risks:</strong>{risks_html}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='small'><strong>Recommendation:</strong> {escape(rec.strip() or 'No recommendation.')}</div>", unsafe_allow_html=True)
        st.markdown("<hr/>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

# -----------------
# Mode: Ask (QA)
# -----------------
def run_qa(context):
    st.markdown("<div class='card'><div class='section-title'>💬 Ask a short question (one line)</div>", unsafe_allow_html=True)
    q = st.text_input("Ask a short question about the uploaded document", "")
    if st.button("Answer"):
        if not context.strip():
            st.warning("No context available. Upload or paste text in Analyze first.")
            return
        if not q.strip():
            st.warning("Ask a short question.")
            return
        out = call_model(prompt_answer_question(q, context), max_tokens=120)
        st.markdown(f"<div class='small'><strong>Answer (grounded):</strong> {escape(out)}</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# -----------------
# Mode: Compare
# -----------------
def run_compare():
    st.markdown("<div class='card'><div class='section-title'>🔁 Compare Two Contracts</div>", unsafe_allow_html=True)
    cA = st.file_uploader("Upload Contract A (PDF)", key="compA", type=["pdf"])
    textA = st.text_area("Or paste Contract A text", key="textA", height=140)
    cB = st.file_uploader("Upload Contract B (PDF)", key="compB", type=["pdf"])
    textB = st.text_area("Or paste Contract B text", key="textB", height=140)
    if st.button("Run Comparison"):
        A = ""
        B = ""
        if cA:
            A = extract_text_from_pdf_bytes(cA.read())
        elif textA and textA.strip():
            A = clean_text(textA)
        if cB:
            B = extract_text_from_pdf_bytes(cB.read())
        elif textB and textB.strip():
            B = clean_text(textB)
        if not A or not B:
            st.warning("Both Contract A and B must have text (upload or paste).")
            return
        # create short summaries for both (quick)
        sA = call_model(prompt_summarize_section(A), max_tokens=80)
        sB = call_model(prompt_summarize_section(B), max_tokens=80)
        # build compare prompt and call
        cmp_prompt = prompt_compare(sA, sB)
        comp = call_model(cmp_prompt, max_tokens=300)
        st.markdown("<div class='small'><strong>Quick A summary:</strong> " + escape(sA) + "</div>", unsafe_allow_html=True)
        st.markdown("<div class='small'><strong>Quick B summary:</strong> " + escape(sB) + "</div>", unsafe_allow_html=True)
        st.markdown("<hr/>", unsafe_allow_html=True)
        st.markdown("<div class='section-title'>🔎 Comparison (LLM)</div>", unsafe_allow_html=True)
        # display plain text result (the LLM will already include emojis)
        st.text_area("Comparison result (short)", value=comp, height=220)
    st.markdown("</div>", unsafe_allow_html=True)

# -----------------
# Main runner
# -----------------
# Obtain source_text from upload/manual
source_text = ""
if uploaded:
    try:
        data = uploaded.read()
        source_text = extract_text_from_pdf_bytes(data)
    except Exception:
        source_text = ""
if text_manual and not source_text:
    source_text = clean_text(text_manual)

if mode == "Analyze":
    run_analyze(source_text)
elif mode == "Ask (QA)":
    run_qa(source_text)
elif mode == "Compare":
    run_compare()
else:
    st.markdown("<div class='card'><div class='section-title'>Welcome</div><div class='small muted'>Choose Analyze to upload & summarize, Ask to query a doc, or Compare two contracts.</div></div>", unsafe_allow_html=True)

# -----------------
# Footer: small help
# -----------------
st.markdown("<div style='margin-top:10px' class='muted small'>Tip: Keep uploaded PDFs under 20 pages for best results. For long documents, paste a relevant clause into the QA box.</div>", unsafe_allow_html=True)
