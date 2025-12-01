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

# Build document text from PDF + manual text (merge both)
doc_text = ""

# If PDF uploaded — add its text
if uploaded_pdf:
    pdf_text = extract_text_from_pdf_bytes(uploaded_pdf.read())
    doc_text += pdf_text

# If manual text typed — add it too
if manual_text.strip():
    doc_text += "\n" + clean_text(manual_text)

# Store final merged text
st.session_state.document_text = doc_text.strip()


# ------------------------------
# PROCESS BUTTON
# ------------------------------
if st.button("Send", use_container_width=True):

    if not st.session_state.document_text.strip():
        st.error("❌ Upload a PDF or paste text first.")
        st.stop()

    # Question is optional
    if not question.strip():
        question = ""


    # STRICT PROMPT – one page only
    compact_prompt = f"""
You are LegalEase — you must answer EXACTLY like a helpful assistant
that explains everything clearly, like ChatGPT.

STYLE RULES:
- Understand and interpret basic, broken, simple, or informal English questions
- Use short, meaningful bullet points (not 1–2 word bullets)
- Use bold text for important phrases (allowed for highlighting)
- You may highlight key terms using **bold** only (no HTML tags)
- Use emojis like ✔️ ⚠️ 📌 ➤ when useful
- Use headings exactly like this:

📘 Summary  
📌 Key Clauses  
⚠️ Risks  
✔️ Recommendation  
📥 Answer to Your Question (if a question is provided)

- No long paragraphs (max 1–2 lines)
- No repeating or looping
- No hallucination — use ONLY the document text
- If something is missing in the document, say: **Not mentioned in document**
- Every bullet must be clear and informative (8–18 words)
- Keep tone simple, clean, and human-friendly

OUTPUT FORMAT (FOLLOW EXACTLY):

📘 **Summary** (3 bullets)
- ...

📌 **Key Clauses** (3–5 bullets)
- ...

⚠️ **Risks** (3 bullets)
- ...

✔️ **Recommendation** (1–2 lines)
...

If the user asked a question:
📥 **Answer to Your Question**
- Answer in 1–2 sentences using ONLY document text.
- If unclear or not found, say: **Not mentioned in document**

DOCUMENT:
{st.session_state.document_text}

QUESTION (optional):
{question}
"""



    with st.spinner("Analyzing..."):
        answer = call_model(compact_prompt, max_tokens=500)

    st.subheader("📄 Result")
    st.markdown(answer, unsafe_allow_html=True)



