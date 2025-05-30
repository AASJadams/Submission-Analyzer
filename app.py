# submission-analyzer/app.py

import streamlit as st
import os
import tempfile
import mimetypes
import fitz  # PyMuPDF
import docx2txt
import pandas as pd
import openpyxl
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

st.set_page_config(page_title="Submission Analyzer", layout="wide")
st.title("📄 Commercial Insurance Submission Analyzer")

st.markdown("""
Upload your insurance submission documents in the following order:
1. Discover Form
2. Supplemental Application(s)
3. ACORD Forms
4. Loss Runs

You can also include a website URL or add freeform notes to enrich the analysis.
""")

# Initialize session state
if "summary" not in st.session_state:
    st.session_state.summary = ""
if "analyzed_files" not in st.session_state:
    st.session_state.analyzed_files = set()

uploaded_files = st.file_uploader("Upload Documents", type=["pdf", "docx", "xlsx"], accept_multiple_files=True)
website_url = st.text_input("Website of Insured (optional)")
freeform_text = st.text_area("Freeform Description or Notes (optional)")

# Function to extract text from various formats
def extract_text(file):
    mime_type, _ = mimetypes.guess_type(file.name)
    if file.name.endswith(".pdf"):
        text = ""
        with fitz.open(stream=file.read(), filetype="pdf") as doc:
            for page in doc:
                text += page.get_text()
        return text
    elif file.name.endswith(".docx"):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
            tmp.write(file.read())
            tmp_path = tmp.name
        text = docx2txt.process(tmp_path)
        os.remove(tmp_path)
        return text
    elif file.name.endswith(".xlsx"):
        df_all = pd.read_excel(file, sheet_name=None)
        text = ""
        for sheet, df in df_all.items():
            text += df.to_string(index=False)
        return text
    else:
        return ""

# Fetch and clean website content
def fetch_website_content(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.text, "html.parser")
        return soup.get_text(separator=" ", strip=True)
    except Exception:
        return ""

# Aggregate all content
all_text = ""

for file in uploaded_files:
    if file.name not in st.session_state.analyzed_files:
        extracted = extract_text(file)
        all_text += f"\n\n---\n\n# File: {file.name}\n\n" + extracted
        st.session_state.analyzed_files.add(file.name)

if website_url:
    all_text += "\n\n---\n\n# Website Content\n\n" + fetch_website_content(website_url)

if freeform_text:
    all_text += "\n\n---\n\n# Freeform Notes\n\n" + freeform_text

if st.button("🧠 Analyze Submission"):
    if all_text.strip():
        with st.spinner("Analyzing the submission and generating summary..."):
            prompt = f"""
You are a commercial insurance analyst. Review the following submission documents and provide a structured executive summary. Use bullet points where helpful. Use the following format:

**Executive Summary**
Brief summary.

**Business Overview**
- Named Insured:
- Locations:
- Years in Business:
- Nature of Operations:

**Insurance Coverage**
- Requested Coverage:

**Loss History**
- Summary:

**Fleet & Drivers**
- Vehicles:
- Drivers:

**Description of Operations**
Clear business operations summary.

**Suggested Codes**
- SIC:
- NAICS:
- General Liability Class Codes:

**Underwriting Consideration**
Based on the submission, analyze if BITCO, United Fire Group, The Hanover, EMC, FCCI, Liberty Mutual, RT Specialty, or others might write this risk.

Submission content:
"""
            prompt += all_text

            response = client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            result = response.choices[0].message.content
            st.session_state.summary = result

    else:
        st.warning("Please upload at least one document or enter notes.")

if st.session_state.summary:
    st.markdown("---")
    st.markdown(st.session_state.summary)

# Show which files were already analyzed
if st.session_state.analyzed_files:
    st.markdown("#### 📂 Files Already Analyzed:")
    for fname in st.session_state.analyzed_files:
        st.markdown(f"- {fname} ✅")
