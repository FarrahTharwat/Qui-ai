from fastapi import APIRouter, HTTPException
from bson import ObjectId
from models import TrackRequest
from database import progress_collection
from rules import is_tracking_allowed

router = APIRouter()

@router.post("/track_progress/")
async def track_progress(data: TrackRequest):
    # Validate tracking rule
    await is_tracking_allowed(data.activity_type)

    try:
        user_id = ObjectId(data.user_id)
        activity_id = ObjectId(data.activity_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ObjectId format")

    # Create progress record
    progress_entry = {
        "user_id": user_id,
        "activity_id": activity_id,
        "activity_type": data.activity_type.lower(),
        "metadata": data.metadata or {},
        "completed": False
    }

    await progress_collection.insert_one(progress_entry)
    return {"message": "Progress tracked successfully"}