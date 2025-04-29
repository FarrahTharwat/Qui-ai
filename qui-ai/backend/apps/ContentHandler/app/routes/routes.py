# app/routes.py
from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse
import os
from app.utils.pdf_handler import extract_text_from_pdf
from app.utils.azure_cleaner import clean_text_azure  # Import Azure cleaning function

router = APIRouter()

UPLOAD_DIR = './uploads/'
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload/")
async def upload_file(file: UploadFile = File(...)):
    try:
        # Save the uploaded file temporarily
        file_location = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_location, "wb") as buffer:
            buffer.write(await file.read())
        
        # Extract text from the uploaded PDF
        extracted_text = extract_text_from_pdf(file_location)
        
        # Clean the extracted text using Azure Text Analytics
        cleaned_text = clean_text_azure(extracted_text)
        
        # Return cleaned text as response (for now)
        return {"filename": file.filename, "cleaned_text": cleaned_text[:500]}  # Return the first 500 chars
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=400)
