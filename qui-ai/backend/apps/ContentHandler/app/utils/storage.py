# app/services/storage.py
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

load_dotenv()
TEXT_DIR = "data/texts"
os.makedirs(TEXT_DIR, exist_ok=True)

# app/services/storage.py (updated)

# Raw text handling
def save_raw_text(file_id, raw_text):
    path = os.path.join(TEXT_DIR, f"{file_id}_raw.txt")
    with open(path, "w", encoding="utf-8", errors="replace") as f:
        f.write(raw_text)

def load_raw_text(file_id):
    path = os.path.join(TEXT_DIR, f"{file_id}_raw.txt")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()

# Cleaned text handling (keep existing save_cleaned_text/load_cleaned_text)

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



def get_db_connection():
    return psycopg2.connect(
        dbname=os.getenv("PGDATABASE"),
        user=os.getenv("PGUSER"),
        password=os.getenv("PGPASSWORD"),
        host=os.getenv("PGHOST"),
        port=os.getenv("PGPORT"),
        cursor_factory=RealDictCursor
    )

def save_book_texts(book_id, title, raw_text, cleaned_text, final_text):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO books (id, title, raw_text, cleaned_text, final_cleaned_text)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            raw_text = EXCLUDED.raw_text,
            cleaned_text = EXCLUDED.cleaned_text,
            final_cleaned_text = EXCLUDED.final_cleaned_text
    """, (book_id, title, raw_text, cleaned_text, final_text))

    conn.commit()
    cur.close()
    conn.close()
