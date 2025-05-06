from fastapi import APIRouter, UploadFile, File, HTTPException
import os
import shutil
from uuid import uuid4
from datetime import datetime

from app.utils.pdf_utils import extract_text_from_pdf
from app.services.cleaning_model import ai_clean_text, refine_cleaned_text
from app.utils.storage import save_raw_text, save_cleaned_text, load_raw_text, load_cleaned_text, save_book_texts
from app.utils.comparison import generate_comparison_pdf, generate_diff_html
from fastapi.responses import FileResponse

# If using a DB later, import your model here
# from app.models import UploadedFile (SQLAlchemy)

router = APIRouter(tags=["Upload"])
UPLOAD_DIR = "static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    file_id = str(uuid4())
    filename = f"{file_id}.pdf"
    pdf_path = os.path.join(UPLOAD_DIR, filename)

    # Save file
    with open(pdf_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Extract and save raw text
    raw_text = extract_text_from_pdf(pdf_path)
    save_raw_text(file_id, raw_text)

    # 🔥 Optional: Insert into DB later
    # db.insert_uploaded_file(file_id=file_id, filename=file.filename, created_at=datetime.now())

    return {
        "message": "File uploaded and text extracted",
        "file_id": file_id,
        "raw_excerpt": raw_text[:500]
    }


@router.post("/clean/{file_id}")
async def clean_uploaded_text(file_id: str):
    cleaned_path = f"data/texts/{file_id}_cleaned.txt"

    if os.path.exists(cleaned_path):
        print("⚠️ Already cleaned. Skipping cleaning step.")
        cleaned_text = load_cleaned_text(file_id)
        raw_text = load_raw_text(file_id)
        final_cleaned = refine_cleaned_text(cleaned_text)
    else:
        raw_text = load_raw_text(file_id)
        if not raw_text:
            raise HTTPException(status_code=404, detail="Raw text not found")

        cleaned_text = ai_clean_text(raw_text)
        final_cleaned = refine_cleaned_text(cleaned_text)
        save_cleaned_text(file_id, final_cleaned)

    save_book_texts(
        book_id=file_id,
        title="Uploaded Book",
        raw_text=raw_text,
        cleaned_text=cleaned_text,
        final_text=final_cleaned
    )

    return {
        "message": "Text cleaned and saved to database",
        "file_id": file_id,
        "excerpt": final_cleaned[:700]
    }




@router.get("/compare/{file_id}")
async def get_comparison_pdf(file_id: str):
    pdf_path = f"data/comparisons/{file_id}_comparison.pdf"
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="Comparison not found")
    return FileResponse(pdf_path, media_type="application/pdf")


