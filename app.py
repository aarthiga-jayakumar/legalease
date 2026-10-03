import streamlit as st

from core import (
    InvalidDocumentError,
    analyze,
    clean_text,
    extract_text_from_pdf_bytes,
)

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

    try:
        with st.spinner("Analyzing..."):
            answer = analyze(doc, question)
    except InvalidDocumentError as exc:
        st.error(f"❌ {exc}")
        st.stop()
    except RuntimeError as exc:
        st.error(f"❌ Configuration problem: {exc}")
        st.stop()

    st.markdown("<div class='result-card'>", unsafe_allow_html=True)
    st.markdown("### 📄 Final One-Page Result")
    st.markdown(answer)
    st.markdown("</div>", unsafe_allow_html=True)
