import streamlit as st
import zipfile
import os
import tempfile
import json
import pandas as pd
from doctr.io import DocumentFile
from doctr.models import ocr_predictor
from PIL import Image
from docx import Document

ocr_model = ocr_predictor(pretrained=True)

SUPPORTED_EXTS = ['.pdf', '.png', '.jpg', '.jpeg', '.docx', '.xlsx', '.xls', '.csv']

def extract_text_from_file(file_path, ext):
    text = ""
    if ext in ['.pdf', '.png', '.jpg', '.jpeg']:
        doc = DocumentFile.from_images(file_path) if ext in ['.png', '.jpg', '.jpeg'] else DocumentFile.from_pdf(file_path)
        result = ocr_model(doc)
        for block in result.pages[0].blocks:
            for line in block.lines:
                text += ' '.join([word.value for word in line.words]) + "\n"
    elif ext == '.docx':
        doc = Document(file_path)
        text = '\n'.join([para.text for para in doc.paragraphs])
    elif ext in ['.xlsx', '.xls']:
        df = pd.read_excel(file_path)
        text = df.to_string(index=False)
    elif ext == '.csv':
        df = pd.read_csv(file_path)
        text = df.to_string(index=False)
    return text.strip()

def process_file(uploaded_file):
    suffix = os.path.splitext(uploaded_file.name)[-1].lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
        tmp_file.write(uploaded_file.read())
        tmp_path = tmp_file.name
    return tmp_path, suffix

def main():
    st.title("Document Text Extractor with DOCTR")
    uploaded_file = st.file_uploader("Upload file (zip, pdf, docx, png, jpg, xlsx, csv)", type=['zip'] + [ext[1:] for ext in SUPPORTED_EXTS])

    if uploaded_file:
        if uploaded_file.name.endswith('.zip'):
            with tempfile.TemporaryDirectory() as extract_dir:
                zip_path, _ = process_file(uploaded_file)
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
                    json_outputs = []
                    for filename in os.listdir(extract_dir):
                        full_path = os.path.join(extract_dir, filename)
                        ext = os.path.splitext(filename)[-1].lower()
                        if ext in SUPPORTED_EXTS:
                            st.subheader(f"📄 File: {filename}")
                            try:
                                text = extract_text_from_file(full_path, ext)
                                st.text_area("Extracted Text", text, height=200)
                                approved = st.radio(f"Do you approve the output for {filename}?", ("Approve", "Decline"), key=filename)
                                if approved == "Approve":
                                    json_outputs.append((filename, {"filename": filename, "text": text}))
                            except Exception as e:
                                st.warning(f"Could not process {filename}: {e}")

                    if json_outputs:
                        output_zip = os.path.join(extract_dir, "output_jsons.zip")
                        with zipfile.ZipFile(output_zip, 'w') as zipf:
                            for fname, content in json_outputs:
                                json_name = os.path.splitext(fname)[0] + ".json"
                                json_path = os.path.join(extract_dir, json_name)
                                with open(json_path, 'w', encoding='utf-8') as f:
                                    json.dump(content, f, indent=2)
                                zipf.write(json_path, arcname=json_name)
                        with open(output_zip, 'rb') as f:
                            st.download_button("📦 Download All Approved JSONs", f, file_name="approved_outputs.zip")

        else:
            path, ext = process_file(uploaded_file)
            if ext in SUPPORTED_EXTS:
                st.subheader(f"📄 File: {uploaded_file.name}")
                try:
                    text = extract_text_from_file(path, ext)
                    st.text_area("Extracted Text", text, height=200)
                    approved = st.radio("Do you approve the output?", ("Approve", "Decline"))
                    if approved == "Approve":
                        json_data = {
                            "filename": uploaded_file.name,
                            "text": text
                        }
                        json_str = json.dumps(json_data, indent=2)
                        st.download_button("📥 Download JSON", json_str, file_name="approved_output.json")
                except Exception as e:
                    st.error(f"Error processing file: {e}")
            else:
                st.warning("Unsupported file format.")

if __name__ == "__main__":
    main()
