from fpdf import FPDF
import textwrap
import os


class PDF(FPDF):
    def __init__(self):
        super().__init__()

        # 1. Use absolute path to font file
        font_path = os.path.join(os.path.dirname(__file__), "fonts", "DejaVuSans.ttf")
        if not os.path.exists(font_path):
            raise FileNotFoundError(f"Font not found at {font_path}")



        # 2. Validate font file (add debug print)
        print(f"🔄 Loading font from: {font_path}")  # Debug path

        # 3. Add font
        self.add_font("dejavu", "", font_path, uni=True)
        self.set_font("dejavu", "", 10)

        # 4. Configure page
        self.set_auto_page_break(auto=True, margin=15)
        self.add_page()

    def header(self):
        self.set_font("dejavu", "", 12)
        self.cell(90, 10, "Original Text", border=1, align="C")
        self.cell(0, 10, "Cleaned Text", border=1, align="C")
        self.ln()

    def add_side_by_side(self, left_text, right_text):
        left_lines = textwrap.wrap(left_text, width=60)
        right_lines = textwrap.wrap(right_text, width=60)
        max_lines = max(len(left_lines), len(right_lines))

        for i in range(max_lines):
            left_line = left_lines[i] if i < len(left_lines) else ""
            right_line = right_lines[i] if i < len(right_lines) else ""
            self.cell(90, 5, left_line, border=0)
            self.cell(0, 5, right_line, border=0)
            self.ln()


def create_comparison_pdf(raw_text: str, cleaned_text: str, output_path: str):
    pdf = PDF()

    raw_paragraphs = raw_text.strip().split("\n\n")
    cleaned_paragraphs = cleaned_text.strip().split("\n\n")
    max_len = max(len(raw_paragraphs), len(cleaned_paragraphs))

    for i in range(max_len):
        left = raw_paragraphs[i] if i < len(raw_paragraphs) else ""
        right = cleaned_paragraphs[i] if i < len(cleaned_paragraphs) else ""
        pdf.add_side_by_side(left, right)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    pdf.output(output_path)


