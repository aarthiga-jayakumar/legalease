import streamlit as st
import json

st.title("📘 LegalEase – Contract Analyzer")

uploaded = st.file_uploader("Upload a contract PDF", type=["pdf"])

if uploaded:
    st.success("PDF uploaded successfully!")
    st.info("This is a placeholder UI. AI extraction happens next.")

# Load processed output
try:
    with open("final_output.json", "r") as f:
        data = json.load(f)
    
    st.subheader("📌 Extracted Results")
    for item in data:
        st.markdown(f"### 🔹 Section: {item['heading']}")
        st.markdown(f"**Summary:** {item['summary']}")
        st.markdown(f"**Clauses:** {item['clauses']}")
        st.markdown(f"**Risks:** {item['risks']}")
        st.markdown("---")

except:
    st.warning("No processed output found yet.")
