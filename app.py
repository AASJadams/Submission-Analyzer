import streamlit as st
import os
import docx
from PyPDF2 import PdfReader
from openai import OpenAI

# --- Initialize OpenAI client with API key ---
client = OpenAI(api_key="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")

# --- Streamlit Page Setup ---
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

# --- Extract Text from Uploaded Files ---
def extract_text(file):
    text = ""
    if file.name.endswith(".pdf"):
        reader = PdfReader(file)
        for page in reader.pages:
            text += page.extract_text() or ""
    elif file.name.endswith(".docx"):
        doc = docx.Document(file)
        for para in doc.paragraphs:
            text += para.text + "\n"
    elif file.name.endswith(".txt"):
        text = file.read().decode("utf-8")
    else:
        text = "[Unsupported file type]"
    return text

# --- Get ChatGPT Response ---
def get_chat_response(prompt):
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",  # Changed from "gpt-4"
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"[ERROR] {e}"

# --- File Uploader UI ---
uploaded_files = st.file_uploader(
    "Upload submission documents",
    type=["pdf", "docx", "txt"],
    accept_multiple_files=True
)

# --- Analyze Button ---
if st.button("Analyze Submission"):
    if not uploaded_files:
        st.warning("Please upload at least one document.")
    else:
        with st.spinner("Extracting and analyzing..."):
            all_text = ""
            for file in uploaded_files:
                all_text += extract_text(file) + "\n"

            prompt = f"""You are an insurance underwriting assistant. Read the following submission documents and provide a summary of business operations, key risk factors, and underwriting considerations:\n\n{all_text}"""

            response = get_chat_response(prompt)

        st.markdown("### 📋 AI Summary")
        st.write(response)
