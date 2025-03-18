from fastapi import APIRouter, HTTPException
from bson import ObjectId
from database import user_collection, lesson_collection, progress_collection
from models import ProgressRequest

router = APIRouter()

async def is_valid_objectid(id_str):
    return ObjectId.is_valid(id_str)

@router.post("/track_progress/")
async def track_progress(request: ProgressRequest):
    if not is_valid_objectid(request.user_id) or not is_valid_objectid(request.lesson_id):
        raise HTTPException(status_code=400, detail="Invalid ObjectId format.")

    user_id = ObjectId(request.user_id)
    lesson_id = ObjectId(request.lesson_id)

    # ✅ Check if user exists, create if not
    user = await user_collection.find_one({"_id": user_id})
    if not user:
        new_user = {"_id": user_id, "name": "New User"}
        await user_collection.insert_one(new_user)

    # ✅ Check if lesson exists, create if not
    lesson = await lesson_collection.find_one({"_id": lesson_id})
    if not lesson:
        new_lesson = {"_id": lesson_id, "title": "New Lesson"}
        await lesson_collection.insert_one(new_lesson)

    # ✅ Check if progress exists
    existing_progress = await progress_collection.find_one({"user_id": user_id, "lesson_id": lesson_id})

    if existing_progress:
        # ✅ Update XP and check completion
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

    # ✅ Create new progress record
    progress_entry = {
        "user_id": user_id,
        "lesson_id": lesson_id,
        "xp_gained": request.xp_gained,
        "completed": request.xp_gained >= 100
    }

    result = await progress_collection.insert_one(progress_entry)
    return {"message": "Progress recorded", "progress_id": str(result.inserted_id)}
