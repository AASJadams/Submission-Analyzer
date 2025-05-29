import os
import time
import tempfile
import fitz  # PyMuPDF
import pandas as pd
import docx2txt
import streamlit as st
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key="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")

st.set_page_config(page_title="Insurance Submission Analyzer", layout="wide")

st.title("📄 Commercial Insurance Submission Analyzer")
st.markdown("Upload documents like supplemental apps, ACORDs, loss runs, etc. Optionally add manual notes or a business website.")

# Keep track of analyzed files
if "analyzed_files" not in st.session_state:
    st.session_state.analyzed_files = []
if "all_text" not in st.session_state:
    st.session_state.all_text = ""

# Upload and process files
uploaded_files = st.file_uploader("Upload submission documents", type=["pdf", "docx", "xlsx"], accept_multiple_files=True)

manual_input = st.text_area("📝 Optional: Type any additional information about the business or risk")

website_url = st.text_input("🌐 Optional: Enter the insured’s website URL")

def extract_text(file):
    tmp_path = None
    text = ""
    try:
        suffix = os.path.splitext(file.name)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            tmp_file.write(file.read())
            tmp_path = tmp_file.name

        if suffix == ".pdf":
            with fitz.open(tmp_path) as doc:
                for page in doc:
                    text += page.get_text()
        elif suffix == ".docx":
            text = docx2txt.process(tmp_path)
        elif suffix == ".xlsx":
            df = pd.read_excel(tmp_path, sheet_name=None)
            for sheet in df.values():
                text += sheet.to_string(index=False)
    finally:
        time.sleep(1)
        if tmp_path:
            try:
                os.remove(tmp_path)
            except PermissionError:
                pass
    return text

def scrape_website_text(url):
    try:
        response = requests.get(url, timeout=5)
        soup = BeautifulSoup(response.text, "html.parser")
        return ' '.join([p.get_text(separator=" ") for p in soup.find_all("p")])
    except Exception:
        return ""

if uploaded_files:
    for file in uploaded_files:
        if file.name not in st.session_state.analyzed_files:
            file_text = extract_text(file)
            st.session_state.all_text += f"\n\nFrom file: {file.name}\n{file_text}"
            st.session_state.analyzed_files.append(file.name)

if manual_input:
    st.session_state.all_text += f"\n\nManual Notes:\n{manual_input}"

if website_url:
    website_content = scrape_website_text(website_url)
    if website_content:
        st.session_state.all_text += f"\n\nWebsite Content from {website_url}:\n{website_content}"

if st.session_state.all_text:
    st.markdown("### 📊 Submission Summary")
    with st.spinner("Analyzing submission..."):
        prompt = f"""
Analyze the following insurance submission data and generate an executive summary for an underwriter. The output should be formatted using section titles in **bold**, and include bullet points where appropriate.

Sections to include:
- **Executive Summary**
- **Business Overview**
- **Insurance Coverage**
- **Loss History**
- **Fleet & Drivers**
- **🛠️ Description of Operations**
- **🏢 Underwriting Consideration** (analyze if BITCO, United Fire Group, The Hanover, EMC, FCCI, Liberty Mutual, RT Specialty or other carriers might write this)
- **📊 NAICS, SIC, and General Liability (GL) Class Codes**

Content:
{st.session_state.all_text}
"""

        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )

        result = response.choices[0].message.content
        st.markdown(result.replace("###", "**").replace("\n- ", "\n• "), unsafe_allow_html=True)

    # Show which files have been analyzed
    st.markdown("---")
    st.markdown("**✅ Analyzed Files:**")
    for name in st.session_state.analyzed_files:
        st.markdown(f"- {name}")
