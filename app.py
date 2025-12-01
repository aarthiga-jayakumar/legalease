import streamlit as st
import pdfplumber
import io
import re
import os
from groq import Groq

# ------------------------------
# CONFIG
# ------------------------------
MODEL_ID = "llama-3.3-70b-versatile"
GROQ_KEY = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=GROQ_KEY)

# ------------------------------
# HELPERS
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
    with pdfplumber.open(fp) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages]
    return clean_text("\n".join(pages))

def call_model(prompt, max_tokens=700):
    resp = client.chat.completions.create(
        model=MODEL_ID,
        messages=[
            {"role": "system",
             "content":
             "You are a smart legal assistant. You speak in simple English, "
             "give helpful and correct answers, and format cleanly using headings and bullet points."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=max_tokens
    )
    return resp.choices[0].message.content.strip()

# ------------------------------
# GOOGLE-STYLE UI
# ------------------------------
st.set_page_config(page_title="LegalEase", layout="wide")

# ---- GOOGLE STYLE CSS ----
st.markdown("""
<style>

html, body, [class*="css"]  {
    font-family: 'Inter', sans-serif;
}

.main-title {
    font-size: 36px;
    font-weight: 700;
    color: #1a73e8;
    padding-bottom: 5px;
}

.sub {
    font-size: 16px;
    color: #5f6368;
    margin-bottom: 25px;
}

.card {
    background: #ffffff;
    padding: 22px;
    border-radius: 14px;
    box-shadow: 0 4px 14px rgba(0,0,0,0.08);
    margin-bottom: 20px;
}

.result-card {
    background: #f8fbff;
    padding: 25px;
    border-radius: 16px;
    border-left: 6px solid #1a73e8;
    margin-top: 15px;
}

.send-btn {
    background:#1a73e8;
    color:white;
    border:none;
    padding:10px 20px;
    border-radius:8px;
    font-size:17px;
    font-weight:600;
    width:100%;
}

.send-btn:hover {
    background:#1666d4;
}

</style>
""", unsafe_allow_html=True)

# ------------------------------
# PAGE CONTENT
# ------------------------------
st.markdown("<div class='main-title'>📘 LegalEase — Smart AI Contract Assistant</div>", unsafe_allow_html=True)
st.markdown("<div class='sub'>Upload a contract or paste text. Ask any question. Get a clean one-page Google-style result.</div>", unsafe_allow_html=True)

# Input card
with st.container():
    st.markdown("<div class='card'>", unsafe_allow_html=True)

    uploaded_pdf = st.file_uploader("📁 Upload PDF", type=["pdf"])
    manual_text = st.text_area("✏️ Or paste contract text", height=160)
    question = st.text_input("💬 Ask a question (optional, simple English supported)")

    st.markdown("</div>", unsafe_allow_html=True)

# ------------------------------
# STORE DOCUMENT TEXT
# ------------------------------
if "document_text" not in st.session_state:
    st.session_state.document_text = ""

if uploaded_pdf:
    st.session_state.document_text = extract_text_from_pdf_bytes(uploaded_pdf.read())
    st.success("PDF loaded!")

if manual_text.strip():
    st.session_state.document_text = clean_text(manual_text)

# ------------------------------
# PROCESS BUTTON
# ------------------------------
clicked = st.button("Send", type="primary")

if clicked:

    doc = st.session_state.document_text.strip()

    if not doc:
        st.error("❌ Upload a PDF or paste text first.")
        st.stop()

    if not question.strip():
        question = "Give me a useful overview based on this document."

    final_prompt = f"""
You MUST produce a **one-page clean report**.

STYLE RULES:
- Use **clear headings** (bold allowed)
- Use short bullet points (8–18 words)
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
1–2 sentence answer in **simple English**, based only on the document.

✔️ **Recommendation (max 2 lines)**
Short and practical suggestion.

---------------------------------

DOCUMENT:
{doc}

QUESTION:
{question}
"""

    with st.spinner("Analyzing..."):
        answer = call_model(final_prompt, max_tokens=700)

    st.markdown("<div class='result-card'>", unsafe_allow_html=True)
    st.markdown("### 📄 Final One-Page Result")
    st.markdown(answer)
    st.markdown("</div>", unsafe_allow_html=True)
