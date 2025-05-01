from difflib import HtmlDiff
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from app.utils.storage import load_raw_text, load_cleaned_text


def generate_diff_html(file_id: str) -> str:
    """Generate HTML diff between raw and cleaned text"""
    raw = load_raw_text(file_id) or ""
    cleaned = load_cleaned_text(file_id) or ""

    differ = HtmlDiff()
    return differ.make_file(
        raw.splitlines(),
        cleaned.splitlines(),
        context=True,
        numlines=3,
        title=f"Text Comparison - {file_id}"
    )


def generate_comparison_pdf(file_id: str, output_path: str = None) -> str:
    """Generate side-by-side PDF comparison"""
    raw = load_raw_text(file_id) or ""
    cleaned = load_cleaned_text(file_id) or ""

    if not output_path:
        output_path = f"data/comparisons/{file_id}_comparison.pdf"

    doc = SimpleDocTemplate(output_path, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # Title
    story.append(Paragraph(f"Text Cleaning Comparison: {file_id}", styles['Title']))
    story.append(Spacer(1, 24))

    # Original Section
    story.append(Paragraph("<b>Original Text</b>", styles['Heading2']))
    story.append(Paragraph(raw.replace("\n", "<br/>"), styles['Normal']))
    story.append(Spacer(1, 24))

    # Cleaned Section
    story.append(Paragraph("<b>Cleaned Text</b>", styles['Heading2']))
    story.append(Paragraph(cleaned.replace("\n", "<br/>"), styles['Normal']))

    doc.build(story)
    return output_path