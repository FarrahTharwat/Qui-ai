#!/usr/bin/env python3
"""
Create a simple test PDF file for API testing
"""

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
import os


def create_test_pdf(filename="test.pdf"):
    """Create a simple test PDF file"""

    # Create a PDF with some test content
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter

    # Add title
    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, height - 100, "Test Document for API Testing")

    # Add some content
    c.setFont("Helvetica", 12)
    y_position = height - 150

    test_content = [
        "This is a test PDF document created for API testing purposes.",
        "",
        "Content includes:",
        "• Multiple paragraphs of text",
        "• Different formatting styles",
        "• Sample data for document processing",
        "",
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
        "Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.",
        "Ut enim ad minim veniam, quis nostrud exercitation ullamco.",
        "",
        "This document can be used to test:",
        "1. PDF upload functionality",
        "2. Text extraction capabilities",
        "3. Document processing workflows",
        "4. API response handling",
        "",
        "End of test document."
    ]

    for line in test_content:
        c.drawString(100, y_position, line)
        y_position -= 20

        # Start new page if needed
        if y_position < 100:
            c.showPage()
            y_position = height - 100

    c.save()
    print(f"✅ Created test PDF: {filename}")
    print(f"📄 File size: {os.path.getsize(filename)} bytes")
    return filename


def main():
    # Create test PDF files with different names
    test_files = ["test.pdf", "example.pdf", "sample.pdf"]

    print("Creating test PDF files...")
    for filename in test_files:
        if not os.path.exists(filename):
            create_test_pdf(filename)
        else:
            print(f"📄 {filename} already exists")

    print(f"\n✅ Test PDF files ready in: {os.getcwd()}")


if __name__ == "__main__":
    main()