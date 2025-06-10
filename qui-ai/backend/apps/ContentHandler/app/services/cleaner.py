"""# **CLEANING**"""

import re
from collections import defaultdict
import spacy
import sys

class PDFTextCleaner:
    def __init__(self):
        # 1. First try to load via direct import
        try:
            import en_core_web_sm
            self.nlp = en_core_web_sm.load()
            print("Model loaded via direct import")
            return
        except ImportError:
            pass

        # 2. Try loading via spacy.load with exact version
        try:
            self.nlp = spacy.load("en_core_web_sm-3.7.0")
            print("Model loaded via exact version")
            return
        except OSError:
            pass

        # 3. Try to download and install the model
        try:
            print("Attempting to download en_core_web_sm model...")
            from spacy.cli import download
            download('en_core_web_sm')
            self.nlp = spacy.load('en_core_web_sm')
            print("Model downloaded and loaded successfully")
            return
        except Exception as e:
            print(f"Critical error loading spaCy model: {e}")
            sys.exit(1)  # Exit if we can't load the model

    def detect_repeated_lines_across_pages(self, pages_texts):
        """Identify lines that appear in many pages (likely headers/footers)."""
        line_freq = defaultdict(int)
        for page_text in pages_texts:
            unique_lines = set([line.strip() for line in page_text.splitlines() if line.strip()])
            for line in unique_lines:
                line_freq[line] += 1

        threshold = max(2, len(pages_texts) // 3)
        repeated_lines = {line for line, count in line_freq.items() if count >= threshold}
        return repeated_lines

    def remove_repeated_lines_within_text(self, text):
        """Remove duplicate lines within the same text block."""
        if isinstance(text, list):
            text = "\n".join(text)
        lines = text.splitlines()
        seen = set()
        filtered_lines = []
        for line in lines:
            line_stripped = line.strip()
            if line_stripped and line_stripped not in seen:
                seen.add(line_stripped)
                filtered_lines.append(line)
        return "\n".join(filtered_lines)

    def clean_pages(self, pages_texts):
        """Remove cross-page repeated lines and duplicates within each page."""
        repeated_lines = self.detect_repeated_lines_across_pages(pages_texts)
        cleaned_pages = []

        for page_text in pages_texts:
            filtered_lines = []
            for line in page_text.splitlines():
                if line.strip() not in repeated_lines:
                    filtered_lines.append(line)
            page_cleaned = self.remove_repeated_lines_within_text(filtered_lines)
            cleaned_pages.append(page_cleaned)

        return cleaned_pages

    def is_bullet_or_number(self, line):
        return bool(re.match(r"^(\s*[\-\*\•\u2022]|\s*\d+[\.\)]).+", line))

    def segment_paragraphs_enhanced(self, text):
        """Enhanced paragraph segmentation with bullet handling."""
        lines = text.split('\n')
        paragraphs = []
        buffer = []

        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                if buffer:
                    paragraphs.append(' '.join(buffer))
                    buffer = []
                continue

            if self.is_bullet_or_number(stripped):
                if buffer:
                    paragraphs.append(' '.join(buffer))
                    buffer = []
                paragraphs.append(stripped)
                continue

            if buffer:
                prev_line = buffer[-1]
                if (not prev_line.endswith(('.', '?', '!', ':'))) and stripped[0].islower():
                    buffer.append(stripped)  # continuation
                else:
                    paragraphs.append(' '.join(buffer))
                    buffer = [stripped]
            else:
                buffer = [stripped]

        if buffer:
            paragraphs.append(' '.join(buffer))

        return '\n\n'.join(paragraphs)

    def apply_spacy_sentence_segmentation(self, text):
        """Refine paragraph text with spaCy sentence segmentation."""
        paragraphs = text.split('\n\n')
        refined_paragraphs = []

        for para in paragraphs:
            doc = self.nlp(para)
            sentences = [sent.text.strip() for sent in doc.sents]
            refined_paragraphs.append(' '.join(sentences))

        return '\n\n'.join(refined_paragraphs)

    def process_pages(self, pages_texts):
        """Full cleaning pipeline."""
        cleaned_pages = self.clean_pages(pages_texts)
        processed_pages = []
        for page_text in cleaned_pages:
            processed_pages.append(self.process_page(page_text))
        return "\n\n".join(processed_pages)

    def process_page(self, page_text):
        """Process a single page of text: segment into paragraphs and refine sentences."""
        if not page_text.strip():
            return ""
        paragraph_text = self.segment_paragraphs_enhanced(page_text)
        return self.apply_spacy_sentence_segmentation(paragraph_text)

