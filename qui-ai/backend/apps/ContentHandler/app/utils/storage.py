# app/services/storage.py
import os

TEXT_DIR = "data/texts"
os.makedirs(TEXT_DIR, exist_ok=True)

def save_cleaned_text(file_id, cleaned_text):
    path = os.path.join(TEXT_DIR, f"{file_id}_cleaned.txt")
    with open(path, "w", encoding="utf-8", errors="replace") as f:
        f.write(cleaned_text)

def load_cleaned_text(file_id):
    path = os.path.join(TEXT_DIR, f"{file_id}_cleaned.txt")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()