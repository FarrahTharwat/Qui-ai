from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import os
from app.utils.comparison import (
    generate_comparison_pdf,
    generate_diff_html
)
from app.utils.storage import load_raw_text, load_cleaned_text

router = APIRouter(tags=["Comparison"])
COMPARISON_DIR = 'data/comparisons/'
os.makedirs(COMPARISON_DIR, exist_ok=True)


@router.get("/compare/{file_id}")
async def get_comparison_pdf(file_id: str):
    try:
        # Validate files exist
        raw_text = load_raw_text(file_id)
        cleaned_text = load_cleaned_text(file_id)

        if not raw_text or not cleaned_text:
            raise FileNotFoundError("Comparison content not found")

        # Generate comparison documents
        pdf_path = generate_comparison_pdf(file_id, raw_text, cleaned_text)
        html_path = generate_diff_html(file_id, raw_text, cleaned_text)

        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            filename=f"{file_id}_comparison.pdf"
        )

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Comparison failed: {str(e)}"
        )