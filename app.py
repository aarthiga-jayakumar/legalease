import streamlit as st
import pdfplumber
import json
import os
import re
from groq import Groq

# ---------------------------------------------------------
# LOAD GROQ CLIENT
# ---------------------------------------------------------
groq_key = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=groq_key)

# ---------------------------------------------------------
# TEXT PROCESSING HELPERS
# ---------------------------------------------------------

def clean_text(raw):
    text = re.sub(r" +", " ", raw)
    text = re.sub(r"\n(?=[a-z])", " ", text)
    text = re.sub(r"\n{2,}", "\n\n", text)
    return "\n".join([line.strip() for line in text.splitlines()]).strip()

def extract_sections(text):
    """
    Splits text into sections based on headings.
    """
    pattern = r"(?P<head>(^|\n)([A-Za-z0-9 ._-]{1,50}:?))"
    matches = list(re.finditer(pattern, text))

    sections = []
    for i in range(len(matches)):
        start = matches[i].start()
        end = matches[i+1].start() if i+1 < len(matches) else len(text)

        heading = matches[i].group().strip().replace("\n", "")
        content = text[start:end].replace(heading, "").strip()

        if content:
            sections.append({
                "heading": heading,
                "content": content
            })

    if not sections:
        sections.append({
            "heading": "Full Text",
            "content": text
        })

    return sections


# ---------------------------------------------------------
# LLM FUNCTIONS
# ---------------------------------------------------------

def call_model(prompt):
    """
    Generic Groq call wrapper.
    """
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You are a precise legal assistant."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=600
    )
    return resp.choices[0].message.content.strip()

def summarize_section(text):
    prompt = f"Summarize this section in 3-4 bullet points:\n\n{text}"
    return call_model(prompt)

def extract_clauses(text):
    prompt = f"Extract the important clauses or key points (4-7 bullets):\n\n{text}"
    return call_model(prompt)

def detect_risks(text):
    prompt = f"Identify risks, unclear points, contradictions (3-5 bullets):\n\n{text}"
    return call_model(prompt)


# ---------------------------------------------------------
# PDF HANDLER
# ---------------------------------------------------------

def extract_text_from_pdf(uploaded_file):
    with pdfplumber.open(uploaded_file) as pdf:
        text = "".join([p.extract_text() or "" for p in pdf.pages])
    return clean_text(text)


# ---------------------------------------------------------
# UI START
# ---------------------------------------------------------

st.set_page_config(page_title="LegalEase – Contract Analyzer", layout="wide")
st.title("📘 LegalEase – Contract Analyzer")

st.markdown("Upload a contract PDF **or** enter plain text manually.")
st.divider()

# ---------------------------------------------------------
# PDF UPLOAD SECTION
# ---------------------------------------------------------

st.header("📄 Upload a PDF")
pdf_file = st.file_uploader("Choose a PDF file", type=["pdf"])

# ---------------------------------------------------------
# MANUAL TEXT INPUT SECTION
# ---------------------------------------------------------

st.header("📝 Or Paste Text Manually")
input_text = st.text_area("Type/Paste text here", height=220)

start_button = st.button("Process")

# ---------------------------------------------------------
# PROCESSING LOGIC
# ---------------------------------------------------------

if start_button:

    if pdf_file:
        st.success("PDF uploaded. Extracting text…")
        raw_text = extract_text_from_pdf(pdf_file)

    elif input_text.strip():
        st.success("Using manually entered text…")
        raw_text = clean_text(input_text)

    else:
        st.error("Please upload a PDF or enter some text.")
        st.stop()

    # Split into sections
    st.info("Splitting into sections…")
    sections = extract_sections(raw_text)

    # Process each section
    st.header("📌 Extracted Results")

    for sec in sections:
        heading = sec["heading"]
        content = sec["content"]

        st.subheader(f"🔹 Section: {heading}")

        with st.spinner("Summarizing…"):
            summary = summarize_section(content)
        st.markdown(f"**Summary:** {summary}")

        with st.spinner("Extracting clauses…"):
            clauses = extract_clauses(content)
        st.markdown(f"**Clauses:** {clauses}")

        with st.spinner("Detecting risks…"):
            risks = detect_risks(content)
        st.markdown(f"**Risks:** {risks}")

        st.divider()

st.info("Ready. Upload a PDF or type text to start.")
