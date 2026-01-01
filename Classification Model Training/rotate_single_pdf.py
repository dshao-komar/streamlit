from PyPDF2 import PdfReader, PdfWriter
import os

# === CONFIG ===
PDF_PATH = r"C:\Users\DanShao\OneDrive - Komar Alliance\Production Logs\September 2025\912 Production Logs Manual.pdf"
ROTATION_DEGREES = 270     # 270 = rotate counterclockwise
OVERWRITE = False          # True = replace original; False = create new file

def rotate_pdf(input_path, rotation=270, overwrite=False):
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
    print(f"✅ Saved rotated file: {output_path}")

if __name__ == "__main__":
    rotate_pdf(PDF_PATH, ROTATION_DEGREES, OVERWRITE)
