import os
from PyPDF2 import PdfReader, PdfWriter

# === CONFIG ===
FOLDER_PATH = r"C:\Users\DanShao\OneDrive - Komar Alliance\Production Logs\September 2025"
ROTATION_DEGREES = 90     # use 270 for counterclockwise rotation
OVERWRITE = False          # True = replace originals; False = create new _rotated.pdf files

def rotate_pdf(input_path, rotation=90, overwrite=False):
    reader = PdfReader(input_path)
    writer = PdfWriter()

    for page in reader.pages:
        page.rotate(rotation)
        writer.add_page(page)

    if overwrite:
        output_path = input_path
    else:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_rotated{ext}"

    with open(output_path, "wb") as f_out:
        writer.write(f_out)
    print(f"✅ Rotated: {os.path.basename(output_path)}")

def rotate_all_pdfs(folder_path, rotation=90, overwrite=False):
    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.lower().endswith(".pdf"):
                pdf_path = os.path.join(root, file)
                rotate_pdf(pdf_path, rotation, overwrite)

if __name__ == "__main__":
    rotate_all_pdfs(FOLDER_PATH, ROTATION_DEGREES, OVERWRITE)
    print("\nAll done! OneDrive will auto-sync your rotated PDFs.")
