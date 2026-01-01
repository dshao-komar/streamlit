import os
from PyPDF2 import PdfReader, PdfWriter

# === CONFIG ===
BASE_FOLDER = r"C:\Users\DanShao\OneDrive - Komar Alliance\Production Logs\Classification Model Training\Combined Training Sets"
SKIP_FOLDERS = {"AW1", "Cutter1"}
ROTATION_DEGREES = 270     # rotate counterclockwise
OVERWRITE = False          # True = replace originals; False = create _rotated.pdf files

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
    print(f"✅ Rotated: {os.path.basename(output_path)}")

def rotate_pdfs_in_tree(base_folder, skip_folders, rotation=270, overwrite=False):
    for root, dirs, files in os.walk(base_folder):
        if os.path.basename(root) in skip_folders:
            print(f"⏭️  Skipping folder: {root}")
            dirs[:] = []  # don't descend further
            continue

        for file in files:
            if file.lower().endswith(".pdf"):
                pdf_path = os.path.join(root, file)
                rotate_pdf(pdf_path, rotation, overwrite)

if __name__ == "__main__":
    print(f"🔍 Scanning {BASE_FOLDER} (skipping {', '.join(SKIP_FOLDERS)})...\n")
    rotate_pdfs_in_tree(BASE_FOLDER, SKIP_FOLDERS, ROTATION_DEGREES, OVERWRITE)
    print("\n✅ Done! OneDrive will sync your rotated PDFs automatically.")
