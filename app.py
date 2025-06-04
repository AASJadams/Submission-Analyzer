import streamlit as st
import os
import tempfile
import time
import base64
import fitz  # PyMuPDF
import docx2txt
import openpyxl
import re
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables from .env
load_dotenv()

# OpenAI client setup
client = OpenAI(api_key="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")

st.set_page_config(page_title="Insurance Submission Analyzer", layout="wide")
st.title("📄 Insurance Submission Analyzer")

st.markdown("""
Upload your insurance submission documents in the following order:
1. **Discovery Form**
2. **Supplemental Application(s)**
3. **ACORD Forms**
4. **Loss Runs**

The tool will analyze and summarize the contents for underwriting.
""")

# Session states
if "analyzed_files" not in st.session_state:
    st.session_state.analyzed_files = set()

if "summary_text" not in st.session_state:
    st.session_state.summary_text = ""

if "all_text" not in st.session_state:
    st.session_state.all_text = ""

# Fix broken words
def fix_broken_words(text):
    text = re.sub(r'(\b(?:[a-zA-Z]\s){2,}[a-zA-Z]\b)', lambda m: m.group(0).replace(' ', ''), text)
    text = re.sub(r'(\d)\s(?=\d)', r'\1', text)
    return text

# File text extraction
def extract_text(file):
    suffix = os.path.splitext(file.name)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(file.read())
        tmp_path = tmp.name

    try:
        if file.name.endswith(".pdf"):
            doc = fitz.open(tmp_path)
            text = "\n".join(page.get_text() for page in doc)
            doc.close()
        elif file.name.endswith(".docx"):
            text = docx2txt.process(tmp_path)
        elif file.name.endswith(".xlsx"):
            wb = openpyxl.load_workbook(tmp_path)
            text = ""
            for sheet in wb.worksheets:
                for row in sheet.iter_rows(values_only=True):
                    text += " ".join([str(cell) if cell is not None else "" for cell in row]) + "\n"
            wb.close()
        else:
            text = ""
    finally:
        time.sleep(1)
        try:
            os.remove(tmp_path)
        except PermissionError:
            pass

    return fix_broken_words(text)

# File uploader
uploaded_files = st.file_uploader("Upload submission documents", type=["pdf", "docx", "xlsx"], accept_multiple_files=True)

# Append and update session all_text
if uploaded_files:
    new_text = ""
    for file in uploaded_files:
        if file.name in st.session_state.analyzed_files:
            st.info(f"✅ {file.name} already analyzed.")
            continue

        st.info(f"🔍 Analyzing: {file.name}")
        file_text = extract_text(file)
        new_text += f"\n---\n{file.name}\n---\n{file_text}"
        st.session_state.analyzed_files.add(file.name)

    # Add new content to all_text only if not already present
    if new_text.strip():
        st.session_state.all_text += new_text

# Only run GPT if there is content
if st.session_state.all_text.strip():
    with st.spinner("Processing with GPT..."):
        prompt = f"""
You are an insurance underwriting assistant. Analyze the following insurance submission documents and generate a clean, non-repetitive executive summary using the following format:

**Executive Summary:**
(Concise summary of the business and their insurance request)

**Business Overview:**
- **Named Insured:**
- **Physical Addresses:**
- **Business Type:**
- **Years in Business:**
- **Estimated Annual Revenue:**

**Insurance Coverage Requested:**
- General Liability
- Property
- Business Auto
- Workers Compensation
- Inland Marine
- Excess/Umbrella

**Loss History:**
(Brief summary of major losses, dates, amounts, loss ratio, open claims)

**Fleet & Drivers:**
(Number of vehicles, types, driver info, exposures)

**Description of Operations:**
(Clear breakdown of what the insured does, services/products offered, facility setup, risk exposures, etc.)

**Underwriting Consideration:**
Would any of the following carriers likely write this risk based on the information provided? Please justify for each: 
- BITCO
- United Fire Group
- The Hanover
- EMC
- FCCI
- Liberty Mutual
- RT Specialty
- Other MGAs or standard carriers

**Classification Codes:**
- **NAICS:**
- **SIC:**
- **General Liability Class Code(s):**

Text to analyze:
{st.session_state.all_text}
"""
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a helpful insurance underwriting assistant."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )
        st.session_state.summary_text = response.choices[0].message.content

# Display summary
if st.session_state.summary_text:
    st.markdown("---")
    st.markdown("**📋 Submission Summary**")
    st.markdown(st.session_state.summary_text, unsafe_allow_html=True)

    if st.button("🔄 Clear Summary"):
        st.session_state.summary_text = ""
        st.session_state.all_text = ""
        st.session_state.analyzed_files = set()
        st.success("Summary cleared. You can now re-upload documents.")

# ----------------------------
# 📄 Carrier Report Analyzer
# ----------------------------
import fitz  # PyMuPDF
import re

st.markdown("---")
st.header("📄 Carrier Report Analyzer")

carrier_files = st.file_uploader(
    "Upload one or more carrier PDF reports",
    type=["pdf"],
    accept_multiple_files=True,
    key="carrier_batch_upload"
)

def extract_metrics_from_text(text):
    loss = re.search(r"Loss Ratio[:\s]+(\-?\d+\.?\d*)%", text, re.IGNORECASE)
    growth = re.search(r"Growth[:\s]+(\-?\d+\.?\d*)%", text, re.IGNORECASE)
    retention = re.search(r"Retention[:\s]+(\-?\d+\.?\d*)%", text, re.IGNORECASE)
    return {
        "Loss Ratio": f"{loss.group(1)}%" if loss else "Not found",
        "Growth %": f"{growth.group(1)}%" if growth else "Not found",
        "Retention %": f"{retention.group(1)}%" if retention else "Not found",
    }

def detect_carrier_name(text):
    # You can improve this list over time based on real reports
    known_carriers = ["Texas Mutual", "FCCI", "Liberty Mutual", "Hanover", "EMC", "BITCO"]
    for carrier in known_carriers:
        if carrier.lower() in text.lower():
            return carrier
    return "Unknown Carrier"

if carrier_files:
    st.success(f"{len(carrier_files)} file(s) uploaded.")
    for file in carrier_files:
        doc = fitz.open(stream=file.read(), filetype="pdf")
        text = "\n".join(page.get_text() for page in doc)
        carrier = detect_carrier_name(text)
        metrics = extract_metrics_from_text(text)

        st.markdown(f"### 📘 {carrier}")
        st.markdown(f"- **Loss Ratio:** {metrics['Loss Ratio']}")
        st.markdown(f"- **Retention %:** {metrics['Retention %']}")
        st.markdown(f"- **Growth %:** {metrics['Growth %']}")

