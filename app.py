import streamlit as st 
import fitz
import zipfile
import tempfile
import os
import re
import pandas as pd
import io
import easyocr
from PIL import Image
import pdfplumber
import docx2txt
import numpy as np

# Helper functions
def pdf_to_text_per_page(pdf_path):
    doc = fitz.open(pdf_path)
    page_texts = []
    for page in doc:
        text = page.get_text()
        if not text.strip():
            pix = page.get_pixmap()
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            text = pytesseract.image_to_string(img)
        page_texts.append(text)
    doc.close()
    return page_texts

def extract_tables(pdf_path):
    tables = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            page_tables = page.extract_tables()
            for table in page_tables:
                df = pd.DataFrame(table)
                tables.append((i+1, df))
    return tables

def extract_images(pdf_path):
    images = []
    doc = fitz.open(pdf_path)
    for i, page in enumerate(doc):
        img_list = page.get_images(full=True)
        for img_index, img in enumerate(img_list):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]
            images.append({
                "page": i+1,
                "image": image_bytes,
                "extension": image_ext,
                "name": f"page_{i+1}_img_{img_index+1}.{image_ext}"
            })
    doc.close()
    return images

def extract_fields(text):
    fields = {
        "Emails": re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-z]{2,}", text),
        "Phone Numbers": re.findall(r"\+?\d[\d\s()-]{7,}\d", text)
    }
    return fields

def extract_text_from_txt(file):
    return file.read().decode("utf-8")

def extract_text_from_docx(file):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        tmp.write(file.read())
        tmp_path = tmp.name
    return docx2txt.process(tmp_path)

reader = easyocr.Reader(['en'])
def extract_text_from_image(file):
    try:
        image = Image.open(file)
        image_np = np.array(image)
        result = reader.readtext(image_np)
        text = " ".join([text[1] for text in result])
        return text 
    except Exception as e:
        print(f"Error during OCR: {e}")
        return None

# Streamlit UI
st.title("📄 Document Extractor (No Database)")

uploaded_zip = st.file_uploader("Upload ZIP file containing PDF documents", type=["zip"])
uploaded_files = st.file_uploader("Or upload individual files", type=["pdf", "txt", "docx", "png", "jpg", "jpeg"], accept_multiple_files=True)

def process_pdf_file(file_bytes, file_name):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
            tmp_pdf.write(file_bytes)
            tmp_pdf_path = tmp_pdf.name

        page_texts = pdf_to_text_per_page(tmp_pdf_path)

        for i, text in enumerate(page_texts):
            fields = extract_fields(text)
            st.subheader(f"{file_name} - Page {i+1}")
            for k, v in fields.items():
                st.write(f"**{k}**: {v}")
            with st.expander("Show Text"):
                st.text(text)

        tables = extract_tables(tmp_pdf_path)
        if tables:
            st.markdown("**📊 Extracted Tables:**")
            for page_num, df in tables:
                st.markdown(f"**Table from Page {page_num}**")
                st.dataframe(df)

        images = extract_images(tmp_pdf_path)
        if images:
            st.markdown("**🖼️ Extracted Images:**")
            for img in images:
                st.image(img["image"], caption=img["name"], use_column_width=True)

    except Exception as e:
        st.warning(f"⚠️ Could not process {file_name}: {e}")

# Handle uploaded files
if uploaded_zip:
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = os.path.join(tmpdir, "uploaded.zip")
        with open(zip_path, "wb") as f:
            f.write(uploaded_zip.read())
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(tmpdir)
        for root, _, files in os.walk(tmpdir):
            for file_name in files:
                if file_name.lower().endswith(".pdf"):
                    full_path = os.path.join(root, file_name)
                    with open(full_path, "rb") as pdf_file:
                        process_pdf_file(pdf_file.read(), file_name)

if uploaded_files:
    for uploaded_file in uploaded_files:
        file_name = uploaded_file.name.lower()
        if file_name.endswith(".pdf"):
            process_pdf_file(uploaded_file.read(), uploaded_file.name)
        else:
            if file_name.endswith(".txt"):
                text = extract_text_from_txt(uploaded_file)
            elif file_name.endswith(".docx"):
                text = extract_text_from_docx(uploaded_file)
            elif file_name.endswith((".png", ".jpg", ".jpeg")):
                text = extract_text_from_image(uploaded_file)
            else:
                continue

            fields = extract_fields(text)
            st.subheader(f"{uploaded_file.name}")
            for k, v in fields.items():
                st.write(f"**{k}**: {v}")
            with st.expander("Show Text"):
                st.text(text)

elif not uploaded_zip and not uploaded_files:
    st.info("Please upload a ZIP file or individual documents to get started.")
