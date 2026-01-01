import os
from pathlib import Path
from PyPDF2 import PdfReader, PdfWriter
from pdf2image import convert_from_path
from PIL import Image
import pytesseract

# === CONFIGURATION ===
base_dir = Path(r"C:\Users\DanShao\OneDrive - Komar Alliance\Production Logs\Classification Model Training\Combined Training Sets")
ocr_dir = base_dir / "ocr_fixed"
ocr_dir.mkdir(exist_ok=True)

# Prevent pillow warning on large images
Image.MAX_IMAGE_PIXELS = None

# === OCR + Rotation Fix + Split ===
for pdf_path in base_dir.glob("*.pdf"):
    if "_ocr" in pdf_path.stem.lower():
        continue  # skip already processed OCR files

    print(f"🔹 Processing {pdf_path.name}")

    # Read PDF metadata for rotation flags
    reader = PdfReader(pdf_path)
    rotations = [int(p.get("/Rotate", 0)) for p in reader.pages]

    # Convert pages to images
    pages = convert_from_path(pdf_path, dpi=150)

    # Prepare output folder for this machine
    name_part = pdf_path.stem.lower().split("training set")[0].strip()
    machine_name = name_part.replace("-", "").replace("_", "").replace(" ", "").title()
    machine_dir = base_dir / machine_name
    machine_dir.mkdir(exist_ok=True)

    print(f"📄 Detected {len(pages)} pages → {machine_name}/")

    for i, img in enumerate(pages):
        # Apply rotation correction
        if rotations[i] != 0:
            img = img.rotate(-rotations[i], expand=True)

        # Extra safety: rotate if still landscape
        if img.width > img.height:
            img = img.rotate(90, expand=True)

        # OCR each page to PDF
        text_pdf_bytes = pytesseract.image_to_pdf_or_hocr(img, extension='pdf')
        single_page_path = machine_dir / f"{machine_name}_page{i+1}.pdf"
        with open(single_page_path, "wb") as f:
            f.write(text_pdf_bytes)

    print(f"✅ OCR & split done for {machine_name}")

print("\n🎉 All PDFs processed, rotated, and split successfully!")
