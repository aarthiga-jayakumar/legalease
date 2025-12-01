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

def call_model(prompt, max_tokens=600):
    resp = client.chat.completions.create(
        model=MODEL_ID,
        messages=[
            {"role": "system", "content": "You answer concisely with short bullet points."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=max_tokens
    )
    return resp.choices[0].message.content.strip()

# ------------------------------
# ONE PAGE UI
# ------------------------------
st.set_page_config(page_title="LegalEase — Contract Assistant", layout="wide")

st.title("📘 LegalEase — Smart Contract Assistant")
st.write("Upload a contract or paste text. Ask any question. Get a **one-page** clean result.")

uploaded_pdf = st.file_uploader("📁 Upload PDF", type=["pdf"])
manual_text = st.text_area("✏️ Or paste contract text", height=180)
question = st.text_input("💬 Ask a question about the document")

# Store the document text
if "document_text" not in st.session_state:
    st.session_state.document_text = ""

# Load PDF
if uploaded_pdf:
    st.session_state.document_text = extract_text_from_pdf_bytes(uploaded_pdf.read())
    st.success("PDF loaded successfully!")

# Load manual text
if manual_text.strip():
    st.session_state.document_text = clean_text(manual_text)

# ------------------------------
# PROCESS BUTTON
# ------------------------------
if st.button("Send", use_container_width=True):

    if not st.session_state.document_text.strip():
        st.error("❌ Upload a PDF or paste text first.")
        st.stop()

    if not question.strip():
        st.error("❌ Please type a question.")
        st.stop()

    # STRICT PROMPT – one page only
    compact_prompt = f"""
You MUST produce a one-page result.

RULES:
- Use very short bullet points (max 10–12 words)
- No paragraphs
- No repeating ideas
- No long sentences
- Use emojis like: ✔ ✘ ⚠ ➤ 📌
- Follow EXACT format:

📘 Summary (max 3 bullets)
- ...

📌 Key Clauses (max 4 bullets)
- ...

⚠ Risks (exactly 3 bullets)
- ...

✔ Recommendation (max 2 lines)
Text…

DOCUMENT:
{st.session_state.document_text}

QUESTION:
{question}
"""

    with st.spinner("Analyzing..."):
        answer = call_model(compact_prompt, max_tokens=500)

    st.subheader("📄 Result")
    st.markdown(answer)


