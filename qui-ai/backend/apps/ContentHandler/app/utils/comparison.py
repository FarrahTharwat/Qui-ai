import os
from difflib import HtmlDiff
from app.utils.storage import load_raw_text, load_cleaned_text
from app.utils.pdf_writer import create_comparison_pdf

# Configuration
COMPARISON_HTML_DIR = "data/diffs"
COMPARISON_PDF_DIR = "data/comparisons"
os.makedirs(COMPARISON_HTML_DIR, exist_ok=True)
os.makedirs(COMPARISON_PDF_DIR, exist_ok=True)

def generate_diff_html(file_id: str) -> str:
    """Generate HTML diff file"""
    raw_text = load_raw_text(file_id)
    cleaned_text = load_cleaned_text(file_id)

    if not raw_text:
        raise FileNotFoundError(f"Raw text not found for {file_id}")
    if not cleaned_text:
        raise FileNotFoundError(f"Cleaned text not found for {file_id}")

    # Generate HTML comparison
    differ = HtmlDiff()
    html_diff = differ.make_file(
        raw_text.splitlines(),
        cleaned_text.splitlines(),
        fromdesc="Original Text",
        todesc="Cleaned Text"
    )

    # Save output
    output_path = os.path.join(COMPARISON_HTML_DIR, f"{file_id}_diff.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_diff)

    return output_path

def generate_comparison_pdf(file_id: str) -> str:
    """Generate PDF comparison file"""
    raw_text = load_raw_text(file_id)
    cleaned_text = load_cleaned_text(file_id)

    if not raw_text:
        raise FileNotFoundError(f"Raw text not found for {file_id}")
    if not cleaned_text:
        raise FileNotFoundError(f"Cleaned text not found for {file_id}")

    # Generate PDF
    output_pdf_path = os.path.join(COMPARISON_PDF_DIR, f"{file_id}_comparison.pdf")
    create_comparison_pdf(
        raw_text,
        cleaned_text,
        output_pdf_path
    )

    return output_pdf_path