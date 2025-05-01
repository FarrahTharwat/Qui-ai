from fastapi import APIRouter, HTTPException
from app.services.cleaning_model import ai_clean_text
from app.utils.storage import load_cleaned_text, save_cleaned_text

router = APIRouter(tags=["Clean"])

@router.post("/clean/{file_id}")
async def clean_text(file_id: str):
    try:
        raw_text = load_cleaned_text(file_id)
        if not raw_text:
            raise HTTPException(status_code=404, detail="Text not found for that file_id")

        cleaned = ai_clean_text(raw_text)
        save_cleaned_text(file_id, cleaned)

        return {
            "message": "Text cleaned successfully",
            "file_id": file_id,
            "clean_excerpt": cleaned[:500]  # Preview only
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
