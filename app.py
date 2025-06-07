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
from tenacity import retry, stop_after_attempt, wait_random_exponential

st.set_page_config(page_title="Submission Analyzer", layout="wide")

client = OpenAI(api_key=os.environ["REAL_OPENAI_KEY"])
st.write("🔍 ENV KEY STARTS WITH:", os.environ.get("REAL_OPENAI_KEY", "❌ MISSING")[:12])

# Custom styles
st.markdown(
    """
    <style>
        html, body, [data-testid="stAppViewContainer"] {
            background-color: #07385e;
            color: #fec52d;
        }
        header[data-testid="stHeader"] {
            background-color: #87212e;
        }
        h1, h2, h3, h4, h5, h6, p, label, span, div {
            color: #fec52d !important;
        }
        input, textarea, .stTextInput, .stTextArea, .stFileUploader label {
            color: #07385e !important;
            font-weight: bold;
        }
        section[data-testid="stFileUploader"] label {
            color: #07385e !important;
            font-weight: bold;
        }
        button[kind="primary"] {
            background-color: #07385e !important;
            color: #fec52d !important;
            border: 1px solid #fec52d !important;
        }
        button[kind="primary"]:hover {
            background-color: #052742 !important;
            color: #ffffff !important;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# Display logo
st.image("https://raw.githubusercontent.com/AASJadams/Submission-Analyzer/main/AAS-Logo.png", width=200)

st.title("📄 Commercial Insurance Submission Analyzer")

st.markdown("""
Upload these specific documents and click **Analyze Submission**:
- Discover Form
- Supplemental Application(s)
- ACORD Forms
- Loss Runs

✅ Once analyzed, you can optionally enter the **insured’s website** and click Analyze Submission again.  
✅ After that, feel free to enter any additional notes or descriptions and click Analyze once more.

This step-by-step process helps avoid loading errors and ensures complete results.
""")

# Session state
if "summary" not in st.session_state:
    st.session_state.summary = ""
if "analyzed_files" not in st.session_state:
    st.session_state.analyzed_files = set()
if "extracted_texts" not in st.session_state:
    st.session_state.extracted_texts = {}

# File uploader and inputs
uploaded_files = st.file_uploader("Upload Documents", type=["pdf", "docx", "xlsx"], accept_multiple_files=True)
website_url = st.text_input("Website of Insured (optional)")
freeform_text = st.text_area("Freeform Description or Notes (optional)")

# Extract text
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

# Get website content
def fetch_website_content(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.text, "html.parser")
        return soup.get_text(separator=" ", strip=True)
    except Exception:
        return ""

# Cache extracted text
for file in uploaded_files:
    if file.name not in st.session_state.analyzed_files:
        text = extract_text(file)
        st.session_state.extracted_texts[file.name] = text
        st.session_state.analyzed_files.add(file.name)
    elif file.name not in st.session_state.extracted_texts:
        st.session_state.extracted_texts[file.name] = extract_text(file)

# Retry logic
@retry(stop=stop_after_attempt(5), wait=wait_random_exponential(min=1, max=10))
def get_chat_response(prompt):
    return client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )

if st.button("🧠 Analyze Submission"):
    all_text = ""
    for fname, text in st.session_state.extracted_texts.items():
        all_text += f"\n\n---\n\n# File: {fname}\n\n" + text

    if website_url:
        all_text += "\n\n---\n\n# Website Content\n\n" + fetch_website_content(website_url)

    if freeform_text:
        all_text += "\n\n---\n\n# Freeform Notes\n\n" + freeform_text

    if all_text.strip():
        with st.spinner("Analyzing the submission and generating summary..."):
            prompt = f"""
You are a commercial insurance analyst. Review the following submission documents and provide a structured executive summary. Use bullet points where helpful. Use the following format:

**Submission Results**

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
- List each individual loss including:
  - Date (if available)
  - Amount of the loss
  - Type of loss (e.g., liability, property)
  - Whether it was open/closed or recovered/subrogated

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
Provide a bullet-point list for each of the following carriers:
- BITCO:
- United Fire Group:
- The Hanover:
- EMC:
- FCCI:
- Liberty Mutual:
- RT Specialty:
- Other notable markets:
Each bullet should state if they are a fit and why or why not based on the submission documents.

Submission content:
"""
            prompt += all_text

            try:
                response = get_chat_response(prompt)
                result = response.choices[0].message.content
                st.session_state.summary = result
            except Exception as e:
                st.error(f"❌ OpenAI call failed: {e}")
    else:
        st.warning("Please upload at least one document or enter notes.")

if st.session_state.summary:
    st.markdown("---")
    st.markdown("## 📝 Submission Results")
    st.markdown(st.session_state.summary)

if st.session_state.analyzed_files:
    st.markdown("#### 📂 Files Already Analyzed:")
    for fname in st.session_state.analyzed_files:
        st.markdown(f"- {fname} ✅")
