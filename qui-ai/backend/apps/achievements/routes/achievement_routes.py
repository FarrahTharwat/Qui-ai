from fastapi import APIRouter, Request
from services.xp_service import get_user_xp

router = APIRouter()

@router.get("/check-achievements/{user_id}")
async def check_achievements(user_id: str, request: Request):
    xp = await get_user_xp(user_id)
    awards = []
    if xp >= 100:
        awards.append("100 XP Milestone")
    if xp >= 500:
        awards.append("500 XP Champion")

    await request.app.mongodb["achievements"].insert_one({"user_id": user_id, "awards": awards})
    return {"user_id": user_id, "awards": awards}