import streamlit as st
from pymongo import MongoClient
import pdfplumber
import easyocr
from PIL import Image
import docx2txt
import pandas as pd
from io import BytesIO
import pypdfium2 as pdfium

# MongoDB setup
client = MongoClient("mongodb://localhost:27017/")
db = client["documentDB"]
collection = db["extracted_texts"]

# Initialize EasyOCR reader (English)
reader = easyocr.Reader(['en'], gpu=False)

# === PDF via image conversion ===
def convert_pdf_to_images(file_bytes, scale=300/72):
    pdf_file = pdfium.PdfDocument(BytesIO(file_bytes))
    page_indices = list(range(len(pdf_file)))

    renderer = pdf_file.render(
        pdfium.PdfBitmap.to_pil,
        page_indices=page_indices,
        scale=scale,
    )

    list_final_images = []
    for i, image in zip(page_indices, renderer):
        image_byte_array = BytesIO()
        image.save(image_byte_array, format='jpeg', optimize=True)
        list_final_images.append({i: image_byte_array.getvalue()})

    return list_final_images

def extract_text_with_easyocr(list_dict_final_images):
    image_list = [list(data.values())[0] for data in list_dict_final_images]
    image_content = []

    for index, image_bytes in enumerate(image_list):
        image = Image.open(BytesIO(image_bytes))
        result = reader.readtext(image, detail=0, paragraph=True)
        page_text = "\n".join(result)
        image_content.append(f"--- Page {index + 1} ---\n{page_text.strip()}\n")

    return "\n".join(image_content)

# === Other file types ===
def extract_text_from_image(file):
    image = Image.open(file)
    result = reader.readtext(image, detail=0, paragraph=True)
    return "\n".join(result)

def extract_text_from_docx(file):
    return docx2txt.process(file).strip()

def extract_text_from_excel(file):
    df = pd.read_excel(file)
    return df.to_string(index=False)

# === Streamlit Interface ===
st.title("📄 Universal Document Text Extractor with EasyOCR & MongoDB Saver")

uploaded_file = st.file_uploader("Upload PDF, Image, Word, or Excel file", type=['pdf', 'png', 'jpg', 'jpeg', 'docx', 'xlsx'])

if uploaded_file:
    file_type = uploaded_file.name.split('.')[-1].lower()
    extracted_text = ""

    if file_type == "pdf":
        pdf_bytes = uploaded_file.read()
        images = convert_pdf_to_images(pdf_bytes)
        extracted_text = extract_text_with_easyocr(images)

    elif file_type in ["png", "jpg", "jpeg"]:
        extracted_text = extract_text_from_image(uploaded_file)

    elif file_type == "docx":
        extracted_text = extract_text_from_docx(uploaded_file)

    elif file_type == "xlsx":
        extracted_text = extract_text_from_excel(uploaded_file)

    else:
        st.error("❌ Unsupported file format.")

    if extracted_text:
        st.subheader("📝 Extracted Text")
        st.text_area("Content", extracted_text, height=400)

        if st.button("💾 Save to MongoDB"):
            collection.insert_one({
                "filename": uploaded_file.name,
                "content": extracted_text
            })
            st.success("✅ Text saved to MongoDB successfully!")
