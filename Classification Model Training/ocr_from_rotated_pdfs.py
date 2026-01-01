import sys
from pathlib import Path
from pdf2image import convert_from_path
from PyPDF2 import PdfWriter
from PIL import Image
import pytesseract

# ======= CONFIG =======
# Change this to your target folder (or pass a folder path as the first CLI arg)
BASE_DIR = Path(r"C:\Users\DanShao\OneDrive - Komar Alliance\Production Logs\September 2025")
DPI_CHAIN = [150, 120]  # try these DPIs in order if a page is too large
# ======================

Image.MAX_IMAGE_PIXELS = None  # prevent Pillow "decompression bomb" warnings on big scans

def ocr_pdf(pdf_path: Path, out_path: Path) -> None:
    """OCR all pages of one already-rotated PDF to a single text-searchable PDF."""
    writer = PdfWriter()
    pages_done = 0

    # render pages with a simple DPI backoff for huge pages
    last_err = None
    for dpi in DPI_CHAIN:
        try:
            images = convert_from_path(pdf_path, dpi=dpi)
            last_err = None
            break
        except Exception as e:
            last_err = e
    if last_err:
        raise last_err

    for i, img in enumerate(images, start=1):
        # no rotation here — files are already *_rotated
        pdf_bytes = pytesseract.image_to_pdf_or_hocr(img, extension='pdf')

        temp_page = out_path.parent / f"__temp_{i}.pdf"
        temp_page.write_bytes(pdf_bytes)

        with temp_page.open("rb") as f:
            writer.append(f)
        temp_page.unlink(missing_ok=True)

        pages_done += 1

    with out_path.open("wb") as f:
        writer.write(f)

    print(f"   ✅ {pdf_path.name}  →  {out_path.name}  ({pages_done} pages OCR’d)")

def main():
    base_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE_DIR
    if not base_dir.exists():
        print(f"Folder not found: {base_dir}")
        sys.exit(1)

    # Only files in *this* folder (no recursion), and only those ending with _rotated.pdf
    pdfs = sorted(p for p in base_dir.glob("*_rotated.pdf") if p.is_file())

    if not pdfs:
        print("No *_rotated.pdf files found in the folder.")
        sys.exit(0)

    processed = 0
    for pdf in pdfs:
        # If we already produced an OCR version, skip it
        # Example: "File_rotated.pdf" -> "File_ocr.pdf"
        out_name = pdf.name.replace("_rotated.pdf", "_ocr.pdf")
        out_path = pdf.with_name(out_name)

        # Also skip if user already has an explicit *_rotated_ocr.pdf
        alt_out_path = pdf.with_name(pdf.stem + "_ocr.pdf")  # fallback name
        if out_path.exists() or alt_out_path.exists():
            print(f"   ⏭️  Skipping (already OCR’d): {pdf.name}")
            continue

        try:
            ocr_pdf(pdf, out_path)
            processed += 1
        except Exception as e:
            print(f"   ❌ Error on {pdf.name}: {e}")

    print(f"\n🎉 Done. OCR’d {processed} file(s) in: {base_dir}")

if __name__ == "__main__":
    main()
