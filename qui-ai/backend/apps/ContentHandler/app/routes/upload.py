from fastapi import APIRouter, UploadFile, File, HTTPException
import os
import logging
from uuid import uuid4
from app.services.local_cleaning_model import clean_text_locally
from app.utils.pdf_utils import extract_text_from_pdf
from app.utils.storage import (
    save_raw_text,
    save_cleaned_text,
    load_cleaned_text,
    load_raw_text
)

router = APIRouter(tags=["Upload & Clean"])
logger = logging.getLogger(__name__)
UPLOAD_DIR = "static/uploads"
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
CHUNK_SIZE = 1024 * 1024  # 1MB

os.makedirs(UPLOAD_DIR, exist_ok=True)


def cleanup_files(file_id: str, pdf_path: str):
    """Clean up any created files in case of failure"""
    try:
        # Remove uploaded PDF
        if os.path.exists(pdf_path):
            os.remove(pdf_path)

        # Remove text files
        text_files = [
            f"data/texts/{file_id}_raw.txt",
            f"data/texts/{file_id}_cleaned.txt"
        ]
        for path in text_files:
            if os.path.exists(path):
                os.remove(path)
    except Exception as e:
        logger.warning(f"Error during cleanup: {str(e)}")


@router.post("/upload-and-clean")
async def upload_and_clean(file: UploadFile = File(..., max_size=MAX_FILE_SIZE)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are allowed")

    file_id = str(uuid4())
    filename = f"{file_id}.pdf"
    pdf_path = os.path.join(UPLOAD_DIR, filename)

    try:
        # Save PDF file
        with open(pdf_path, "wb") as buffer:
            while True:
                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break
                buffer.write(chunk)

        # Extract text from PDF
        raw_text = extract_text_from_pdf(pdf_path)
        if not raw_text or raw_text.strip() == "":
            raise HTTPException(400, "Failed to extract text from PDF")

        # Check for existing cleaned text (unlikely but possible in retries)
        existing_cleaned = load_cleaned_text(file_id)
        if existing_cleaned:
            return {
                "message": "Using cached cleaned text",
                "file_id": file_id,
                "clean_excerpt": existing_cleaned[:500]
            }

        # Save raw text using storage function
        save_raw_text(file_id, raw_text)

        # Clean text using local model
        cleaned_text = clean_text_locally(raw_text)
        if not cleaned_text.strip():
            raise HTTPException(500, "Cleaning returned empty result")

        # Save cleaned text using storage function
        save_cleaned_text(file_id, cleaned_text)

        return {
            "message": "File uploaded and cleaned successfully",
            "file_id": file_id,
            "clean_excerpt": cleaned_text[:500]
        }

    except HTTPException as he:
        logger.error(f"Processing error: {str(he.detail)}")
        cleanup_files(file_id, pdf_path)
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        cleanup_files(file_id, pdf_path)
        raise HTTPException(500, detail="File processing failed")
    finally:
        await file.close()