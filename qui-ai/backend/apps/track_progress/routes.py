from fastapi import APIRouter, HTTPException
from bson import ObjectId
from database import user_collection, lesson_collection, progress_collection
from models import ProgressRequest

router = APIRouter()

# Utility function to check if an ObjectId is valid
def is_valid_objectid(id_str):
    return ObjectId.is_valid(id_str)

@router.post("/track_progress/")
async def track_progress(request: ProgressRequest):
    """
    Tracks or updates user progress.
    - Validates user_id and lesson_id are correct ObjectIds.
    - Ensures user and lesson exist.
    - Updates existing progress or creates a new one.
    """

    # Validate ObjectId format
    if not is_valid_objectid(request.user_id) or not is_valid_objectid(request.lesson_id):
        raise HTTPException(status_code=400, detail="Invalid ObjectId format.")

    user_id = ObjectId(request.user_id)
    lesson_id = ObjectId(request.lesson_id)

    # Check if user exists
    user = await user_collection.find_one({"_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail=f"User with ID {request.user_id} not found.")

    # Check if lesson exists
    lesson = await lesson_collection.find_one({"_id": lesson_id})
    if not lesson:
        raise HTTPException(status_code=404, detail=f"Lesson with ID {request.lesson_id} not found.")

    # Check if progress already exists
    existing_progress = await progress_collection.find_one({"user_id": user_id, "lesson_id": lesson_id})

    if existing_progress:
        # Update existing progress
        new_xp = existing_progress["xp_gained"] + request.xp_gained
        completed = new_xp >= 100  # Assuming 100 XP means lesson completion

        await progress_collection.update_one(
            {"_id": existing_progress["_id"]},
            {"$set": {"xp_gained": new_xp, "completed": completed}}
        )

        return {
            "message": "Progress updated",
            "progress_id": str(existing_progress["_id"]),
            "new_xp": new_xp,
            "completed": completed
        }

    else:
        # Create a new progress entry
        progress_entry = {
            "user_id": user_id,  # Store as ObjectId
            "lesson_id": lesson_id,  # Store as ObjectId
            "xp_gained": request.xp_gained,
            "completed": request.xp_gained >= 100
        }

        result = await progress_collection.insert_one(progress_entry)
        return {"message": "Progress recorded", "progress_id": str(result.inserted_id)}


