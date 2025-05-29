import requests
import re
from PyPDF2 import PdfReader


def preprocess_pdf(file_path: str) -> str:
    """Advanced PDF preprocessing"""
    reader = PdfReader(file_path)
    text = []

    for page in reader.pages:
        page_text = page.extract_text()

        # Remove common PDF artifacts
        page_text = re.sub(r'\s{3,}', '\n\n', page_text)  # Fix excessive whitespace
        page_text = re.sub(r'(?<!\n)\n(?!\n)', ' ', page_text)  # Fix mid-line breaks
        page_text = re.sub(r'-\s+(\w)', r'\1', page_text)  # Fix hyphenated words
        page_text = re.sub(r'\bPage\s+\d+\b', '', page_text)  # Remove page numbers

        text.append(page_text.strip())

    return '\n\n'.join(text)


def clean_text_locally(text: str) -> str:
    try:
        # Process in parallel batches
        processed = []
        batch_size = 3  # Adjust based on your GPU memory
        paragraphs = [p for p in text.split('\n\n') if p.strip()]

        for i in range(0, len(paragraphs), batch_size):
            batch = paragraphs[i:i + batch_size]
            response = requests.post(
                "https://c06b-34-106-110-8.ngrok-free.app/clean",
                json={"text": '\n\n'.join(batch)},
                timeout=60
            )
            if response.status_code == 200:
                processed.extend(response.json()["cleaned"].split('\n\n'))
            else:
                processed.extend(batch)  # Fallback to original

        return '\n\n'.join(processed)

    except Exception as e:
        print(f"Error: {str(e)}")
        return text