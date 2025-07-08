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
from tenacity import retry, wait_random_exponential, stop_after_attempt, retry_if_exception_type
import tiktoken
from openai import RateLimitError

# Load environment variables
load_dotenv()

# Model selection
MODEL = os.getenv("OPENAI_MODEL", "gpt-4-turbo")

# OpenAI client setup
client = OpenAI(api_key="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")

# Streamlit setup
st.set_page_config(page_title="Insurance Submission Analyzer", layout="wide")
st.title("\U0001F4C4 Insurance Submission Analyzer")

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

# Extract text from file
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

# Tokenizer & chunking
ENCODING = tiktoken.encoding_for_model("gpt-3.5-turbo")

def split_text_into_chunks(text, max_tokens=3500):
    tokens = ENCODING.encode(text)
    chunks = [tokens[i:i + max_tokens] for i in range(0, len(tokens), max_tokens)]
    return [ENCODING.decode(chunk) for chunk in chunks]

# Retry-wrapped GPT call
@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6), retry=retry_if_exception_type(RateLimitError))
def gpt_call(model, messages):
    return client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.3,
    )

# File uploader
uploaded_files = st.file_uploader("Upload submission documents", type=["pdf", "docx", "xlsx"], accept_multiple_files=True)

if uploaded_files:
    all_file_texts = []
    for file in uploaded_files:
        if file.name in st.session_state.analyzed_files:
            st.info(f"✅ {file.name} already analyzed.")
            continue

        st.info(f"🔍 Analyzing: {file.name}")
        file_text = extract_text(file)
        st.session_state.analyzed_files.add(file.name)
        all_file_texts.append(f"\n---\n{file.name}\n---\n{file_text}")

    if all_file_texts:
        st.session_state.all_text += "\n".join(all_file_texts)

# Only run GPT if there is content
if st.session_state.all_text.strip():
    with st.spinner("Processing with GPT..."):
        combined_summaries = []
        chunks = split_text_into_chunks(st.session_state.all_text)
        for i, chunk in enumerate(chunks):
            st.info(f"✂️ Summarizing chunk {i+1}/{len(chunks)}")
            summary = gpt_call(MODEL, [
                {"role": "system", "content": "You are a helpful insurance underwriting assistant."},
                {"role": "user", "content": f"Summarize the following submission content:\n\n{chunk}"}
            ]).choices[0].message.content
            combined_summaries.append(summary)

        final_prompt = f"""
You are an insurance underwriting assistant. Using the summarized submission content below, generate a clean, non-repetitive executive summary in this format:

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

**Classification Codes:**
- **NAICS:**
- **SIC:**
- **General Liability Class Code(s):**

Summarized Submission Chunks:
{''.join(combined_summaries)}
"""
        response = gpt_call(MODEL, [
            {"role": "system", "content": "You are a helpful insurance underwriting assistant."},
            {"role": "user", "content": final_prompt},
        ])
        st.session_state.summary_text = response.choices[0].message.content

# Display summary
if st.session_state.summary_text:
    st.markdown("---")
    st.markdown("**\U0001F4CB Submission Summary**")
    st.markdown(st.session_state.summary_text, unsafe_allow_html=True)

    if st.button("\U0001F504 Clear Summary"):
        st.session_state.summary_text = ""
        st.session_state.all_text = ""
        st.session_state.analyzed_files = set()
        st.success("Summary cleared. You can now re-upload documents.")
