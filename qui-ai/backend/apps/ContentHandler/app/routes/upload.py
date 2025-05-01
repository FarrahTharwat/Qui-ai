# app/routes/upload.py
from fastapi import APIRouter, UploadFile, File, HTTPException
import os
import shutil
from uuid import uuid4
from app.utils.pdf_utils import extract_text_from_pdf
from app.services.cleaning_model import ai_clean_text
from app.utils.storage import save_cleaned_text

router = APIRouter(tags=["Upload"])

UPLOAD_DIR = "static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    file_id = f"{uuid4()}.pdf"
    file_path = os.path.join(UPLOAD_DIR, file_id)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {"message": "File uploaded successfully", "file_id": file_id}

@router.post("/upload-and-clean")
async def upload_and_clean_pdf(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files allowed")

    file_id = f"{uuid4()}.pdf"
    file_path = os.path.join(UPLOAD_DIR, file_id)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    raw_text = extract_text_from_pdf(file_path)
    cleaned_text = ai_clean_text(raw_text)
    save_cleaned_text(file_id, cleaned_text)  # Save to persistent storage

    return {
        "message": "Text extracted and cleaned",
        "file_id": file_id,
        "excerpt": cleaned_text[:600]
    }