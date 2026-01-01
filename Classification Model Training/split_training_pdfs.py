import os
from pathlib import Path
from PyPDF2 import PdfReader, PdfWriter

# === CONFIGURATION ===
base_dir = Path(r"C:\Users\DanShao\OneDrive - Komar Alliance\Production Logs\Classification Model Training")

# === MAIN LOGIC ===
for pdf_path in base_dir.glob("*.pdf"):
    try:
        # Extract the machine name from filename (everything before "training set")
        name_part = pdf_path.stem.lower().split("training set")[0].strip()
        machine_name = name_part.replace("-", "").replace("_", "").strip().title()

        # Create output folder for this machine
        output_dir = base_dir / machine_name
        output_dir.mkdir(exist_ok=True)

        # Read and split PDF
        reader = PdfReader(pdf_path)
        num_pages = len(reader.pages)
        print(f"Processing {pdf_path.name} → {num_pages} pages → {output_dir}")

        for i in range(num_pages):
            writer = PdfWriter()
            writer.add_page(reader.pages[i])

            output_filename = f"{machine_name}_page{i+1}.pdf"
            output_path = output_dir / output_filename

            with open(output_path, "wb") as out_f:
                writer.write(out_f)

        print(f"✅ Done: {pdf_path.name}")

    except Exception as e:
        print(f"❌ Error processing {pdf_path.name}: {e}")
