# app.py - LegalEase (fixed: shared document via session_state)
# LegalEase — Apple-style homepage + Light/Dark toggle + Analyze / QA / Compare

import streamlit as st
import pdfplumber
import os, re, json, io, time
from groq import Groq
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from html import escape

# ------------------------------
# Config
# ------------------------------
MODEL_ID = "llama-3.3-70b-versatile"
GROQ_KEY = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=GROQ_KEY)

# ------------------------------
# Helper functions
# ------------------------------
def clean_text(raw):
    if not raw:
        return ""
    raw = raw.replace("\r", "")
    raw = re.sub(r"\n{2,}", "\n\n", raw)
    raw = re.sub(r" {2,}", " ", raw)
    return "\n".join([ln.strip() for ln in raw.splitlines()]).strip()

def extract_text_from_pdf_bytes(data):
    fp = io.BytesIO(data)
    try:
        with pdfplumber.open(fp) as pdf:
            pages = [p.extract_text() or "" for p in pdf.pages]
    except Exception:
        return ""
    return clean_text("\n".join(pages))

def call_model(prompt, max_tokens=450):
    resp = client.chat.completions.create(
        model=MODEL_ID,
        messages=[
            {"role":"system","content":"You are a concise assistant. Follow instructions exactly."},
            {"role":"user","content":prompt}
        ],
        max_tokens=max_tokens
    )
    return resp.choices[0].message.content.strip()

def split_sections(text):
    text = clean_text(text)
    if not text:
        return [{"heading":"Full Text","content":""}]
    lines = text.splitlines()
    sections = []
    cur_h = "Section"
    cur = []
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        # detect headings: numbered, ALL CAPS short, or ends with colon
        is_heading = bool(re.match(r"^\d+[\.\)]", s)) or (s.isupper() and len(s) < 80) or s.endswith(":")
        if is_heading and cur:
            sections.append({"heading":cur_h,"content":" ".join(cur)})
            cur = []
            cur_h = s
        elif is_heading:
            cur_h = s
        else:
            cur.append(s)
    if cur:
        sections.append({"heading":cur_h,"content":" ".join(cur)})
    if not sections:
        sections = [{"heading":"Full Text","content":text}]
    return sections

# Strict prompt templates (force short bullets)
def summarize_section(text):
    prompt = f"""Summarize into **at most 3** bullet points.
Rules:
- Output ONLY bullet points (start each with '- ')
- Maximum 3 bullets, each <= 12 words
- No paragraphs, no extra text

Text:
{text}
"""
    return call_model(prompt)

def extract_clauses(text):
    prompt = f"""Extract **up to 4** key clauses (bullet points).
Rules:
- Output up to 4 bullets, each 1 short sentence
- Prefer concrete phrasing: 'Party must...', 'Payment within 30 days', etc.
- If none, return: '- No clear clauses found.'

Text:
{text}
"""
    return call_model(prompt)

def detect_risks(text):
    prompt = f"""List **exactly 3** short risks or unclear items (bullets).
Rules:
- Exactly 3 bullets, each <= 10 words
- Start each with an emoji tag like '⚠️'
- No paragraphs

Text:
{text}
"""
    return call_model(prompt)

def split_passages(text, chunk=700, overlap=100):
    words = text.split()
    if not words:
        return []
    parts = []
    i = 0
    while i < len(words):
        parts.append(" ".join(words[i:i+chunk]))
        i += chunk - overlap
    return parts

def answer_question_grounded(question, text, top_k=3):
    passages = split_passages(text)
    prompt = "Answer concisely (<=2 sentences). If answer not in passages, say 'Not in document.'\n\n"
    for i, p in enumerate(passages[:top_k], start=1):
        prompt += f"Passage {i}:\n{p[:800]}\n\n"
    prompt += f"Question: {question}"
    return call_model(prompt, max_tokens=300)

def highlight_html(content, clauses_text):
    c_esc = escape(content)
    lines = [l.strip("-* \u2022 ") for l in clauses_text.splitlines() if l.strip()]
    out = c_esc
    for l in lines:
        short = l[:80]
        try:
            out, n = re.subn(re.escape(short), f"<mark>{escape(short)}</mark>", out, count=1, flags=re.I)
        except:
            pass
    return out

def build_pdf_bytes(report_json):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    w,h = letter
    y = h - 40
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y, "LegalEase — Compact Report")
    y -= 28
    c.setFont("Helvetica", 10)
    for sec in report_json.get("sections", []):
        heading = sec.get("heading","")
        summary = sec.get("summary","")
        clauses = sec.get("clauses","")
        risks = sec.get("risks","")
        c.drawString(40, y, f"Section: {heading}")
        y -= 12
        for line in summary.splitlines():
            c.drawString(60, y, line[:120])
            y -= 11
            if y < 80:
                c.showPage(); y = h - 40
        for line in clauses.splitlines():
            c.drawString(60, y, line[:120])
            y -= 11
            if y < 80:
                c.showPage(); y = h - 40
        for line in risks.splitlines():
            c.drawString(60, y, line[:120])
            y -= 11
            if y < 80:
                c.showPage(); y = h - 40
        y -= 8
        if y < 80:
            c.showPage(); y = h - 40
    c.save()
    buf.seek(0)
    return buf.read()

# ------------------------------
# UI / Session setup
# ------------------------------
st.set_page_config(page_title="LegalEase", layout="wide")
if "page" not in st.session_state:
    st.session_state.page = "home"

# ensure document storage exists
if "document" not in st.session_state:
    st.session_state["document"] = ""   # plain text of last uploaded/pasted doc
if "doc_name" not in st.session_state:
    st.session_state["doc_name"] = ""

with st.sidebar:
    st.title("LegalEase")
    theme = st.radio("Theme", ["Light", "Dark"], index=0)
    if theme == "Dark":
        st.markdown("<style>body{background:#0b0b0b;color:#e6e6e6} .stApp .block-container{background:#0b0b0b}</style>", unsafe_allow_html=True)
    st.write("")
    st.write("Quick actions")
    if st.button("Home"):
        st.session_state.page = "home"
    if st.button("Analyze"):
        st.session_state.page = "analyze"
    if st.button("Ask (QA)"):
        st.session_state.page = "qa"
    if st.button("Compare"):
        st.session_state.page = "compare"
    st.write("")
    st.caption("Tip: paste a clause to analyze quickly.")

# Home screen
if st.session_state.page == "home":
    st.markdown("<div style='max-width:1000px;margin:20px auto;padding:30px;border-radius:14px'>", unsafe_allow_html=True)
    st.markdown("<h1 style='font-size:34px;margin-bottom:6px'>📘 LegalEase</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color:#555;font-size:15px;margin-top:0'>Upload a contract or paste text — get short summaries, clauses, and risks.</p>", unsafe_allow_html=True)
    st.markdown("<div style='display:flex;gap:18px;margin-top:28px'>", unsafe_allow_html=True)

    def card_html(icon, title, desc, action):
        html = f"""
        <div style='flex:1;border-radius:14px;padding:22px;background:#fff;box-shadow:0 6px 18px rgba(0,0,0,0.06)'>
          <div style='font-size:28px'>{icon}</div>
          <div style='font-weight:700;font-size:18px;margin-top:8px'>{title}</div>
          <div style='color:#666;margin-top:8px'>{desc}</div>
          <div style='margin-top:14px'>
            <button onclick="document.location='#{action}'" style='padding:10px 14px;border-radius:8px;border:none;background:#0a84ff;color:white'>Open</button>
          </div>
        </div>
        """
        return html

    st.markdown(card_html("📝", "Analyze Contract", "Upload PDF or paste text → short summary, clauses, risks.", "analyze"), unsafe_allow_html=True)
    st.markdown(card_html("💬", "Ask Questions", "Ask direct questions about the uploaded text (QA mode).", "qa"), unsafe_allow_html=True)
    st.markdown(card_html("📄", "Compare Contracts", "Upload two contracts and get a concise comparison.", "compare"), unsafe_allow_html=True)
    st.markdown("</div></div>", unsafe_allow_html=True)

    if st.button("Go to Analyze", key="home_go_analyze"):
        st.session_state.page = "analyze"
    if st.button("Go to QA", key="home_go_qa"):
        st.session_state.page = "qa"
    if st.button("Go to Compare", key="home_go_compare"):
        st.session_state.page = "compare"

# ------------------------------
# ANALYZE PAGE
# ------------------------------
if st.session_state.page == "analyze":
    st.header("Analyze Contract — Upload PDF or paste text")
    col1, col2 = st.columns([1,1])
    with col1:
        pdf_file = st.file_uploader("Upload a PDF", type=["pdf"], key="an_pdf")
    with col2:
        manual_text = st.text_area("Or paste text here", height=200, key="an_text")
    # Allow a "Load into session" button so uploaded/pasted doc becomes the canonical session doc
    if st.button("Load document (store for QA & Compare)"):
        if manual_text and manual_text.strip():
            st.session_state["document"] = clean_text(manual_text)
            st.session_state["doc_name"] = "manual text"
            st.success("Manual text loaded into session for QA/Compare.")
        elif pdf_file:
            data = pdf_file.read()
            txt = extract_text_from_pdf_bytes(data)
            if not txt.strip():
                st.warning("PDF text extraction returned empty. Try a different PDF or paste text.")
            else:
                st.session_state["document"] = txt
                st.session_state["doc_name"] = getattr(pdf_file, "name", "uploaded.pdf")
                st.success(f"PDF loaded into session as '{st.session_state['doc_name']}'.")
        else:
            st.error("Please upload a PDF or paste some text to load into session.")
    # Make it explicit what is currently in session
    if st.session_state["document"]:
        st.info(f"Session document: {st.session_state.get('doc_name','(loaded)')[:80]}")
    else:
        st.info("No session document loaded. Use 'Load document' after upload/paste.")

    if st.button("Process Document (produce report)"):
        text = st.session_state.get("document","")
        source = st.session_state.get("doc_name","session")
        if not text.strip():
            st.error("No document loaded. Upload/paste and click 'Load document' first.")
            st.stop()
        with st.spinner("Splitting into sections..."):
            secs = split_sections(text)
        report = {"source": source, "sections": []}
        st.success("Processing sections (short bullets only)...")
        for s in secs:
            h = s.get("heading","Section")
            c = s.get("content","")
            summ = summarize_section(c)
            cls = extract_clauses(c)
            rks = detect_risks(c)
            report["sections"].append({"heading":h,"content":c,"summary":summ,"clauses":cls,"risks":rks})
            # Render compact card for each section
            summ_html = escape(summ).replace("\n","<br/>")
            cls_html = escape(cls).replace("\n","<br/>")
            rks_html = escape(rks).replace("\n","<br/>")
            highlight = highlight_html(c, cls)
            st.markdown(f"<div style='display:flex;gap:12px;margin-top:18px'>", unsafe_allow_html=True)
            st.markdown(f"<div style='flex:1;padding:14px;border-radius:10px;background:#f7fbff'><b style='font-size:16px'>{escape(h)}</b><div style='font-size:12px;color:#666;margin-top:8px'>Source: {escape(source)}</div><div style='margin-top:10px;font-size:13px'>{highlight}</div></div>", unsafe_allow_html=True)
            st.markdown(f"<div style='flex:1;padding:14px;border-radius:10px;background:#fff7f0'><b>Summary</b><div style='margin-top:8px;font-size:13px'>{summ_html}</div></div>", unsafe_allow_html=True)
            st.markdown(f"<div style='flex:1;padding:14px;border-radius:10px;background:#f3fff6'><b>Clauses</b><div style='margin-top:8px;font-size:13px'>{cls_html}</div></div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='padding:12px;border-radius:8px;background:#fff6f6;margin-top:8px'><b>Risks</b><div style='margin-top:8px;font-size:13px'>{rks_html}</div></div>", unsafe_allow_html=True)
            st.markdown("---")
        # download buttons
        st.download_button("⬇️ Download JSON report", data=json.dumps(report, ensure_ascii=False, indent=2), file_name="legal_ease_report.json", mime="application/json")
        pdf_bytes = build_pdf_bytes(report)
        st.download_button("⬇️ Download PDF report", data=pdf_bytes, file_name="legal_ease_report.pdf", mime="application/pdf")

# ------------------------------
# QA PAGE
# ------------------------------
if st.session_state.page == "qa":
    st.header("Ask Questions (QA) — get grounded answers from the loaded document")
    st.write("Document used for QA: " + (st.session_state.get("doc_name") or "None"))
    question = st.text_input("Your question (clear & short)")
    ctx = st.text_area("Optional: paste the context here (overrides session document)", height=200)
    if st.button("Answer"):
        if ctx and ctx.strip():
            context = clean_text(ctx)
        else:
            context = st.session_state.get("document","")
        if not context.strip():
            st.error("No context available. Upload/paste and use 'Load document' on Analyze first, or paste context here.")
            st.stop()
        if not question.strip():
            st.error("Ask a short question.")
            st.stop()
        with st.spinner("Searching and answering..."):
            ans = answer_question_grounded(question, context, top_k=3)
        st.markdown("**Answer (grounded to doc):**")
        st.write(ans)

# ------------------------------
# COMPARE PAGE
# ------------------------------
if st.session_state.page == "compare":
    st.header("Compare Two Contracts — Upload or paste A and B (session doc can be used as A)")
    colA, colB = st.columns(2)
    with colA:
        fileA = st.file_uploader("Contract A (PDF) — or leave empty to use session document", type=["pdf"], key="compA")
        textA = st.text_area("Or paste Contract A text (leave blank to use session)", height=120)
    with colB:
        fileB = st.file_uploader("Contract B (PDF)", type=["pdf"], key="compB")
        textB = st.text_area("Or paste Contract B text", height=120, key="tb")
    if st.button("Run Comparison"):
        # Contract A: prefer pasted, then uploaded, then session document
        if textA and textA.strip():
            A = clean_text(textA); srcA = "manual-A"
        elif fileA:
            A = extract_text_from_pdf_bytes(fileA.read()); srcA = getattr(fileA,"name","A.pdf")
        else:
            # fallback to session document if available
            if st.session_state.get("document","").strip():
                A = st.session_state["document"]; srcA = st.session_state.get("doc_name","session")
            else:
                st.error("Provide Contract A (paste, upload, or load session doc)."); st.stop()
        # Contract B
        if textB and textB.strip():
            B = clean_text(textB); srcB = "manual-B"
        elif fileB:
            B = extract_text_from_pdf_bytes(fileB.read()); srcB = getattr(fileB,"name","B.pdf")
        else:
            st.error("Provide Contract B (paste or upload)."); st.stop()

        st.info("Summarizing both contracts (short bullets)...")
        sA = summarize_section(A)
        cA = extract_clauses(A)
        rA = detect_risks(A)
        sB = summarize_section(B)
        cB = extract_clauses(B)
        rB = detect_risks(B)
        st.markdown("### Quick summaries")
        st.markdown(f"**Contract A**\n\n{sA}")
        st.markdown(f"**Contract B**\n\n{sB}")
        cmp_prompt = f"""
Compare Contract A and Contract B.

Contract A:
{A}

Contract B:
{B}

Write a structured comparison with:
- Key similarities
- Key differences
- Risks
- Which contract is more favorable and why
"""
        comp = call_model(cmp_prompt, max_tokens=400)
        st.markdown("### Comparison (LLM)")
        st.write(comp)

# End
