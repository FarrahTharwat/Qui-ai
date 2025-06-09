from fastapi import APIRouter, Request
from models.xp_input import XPInput
from services.user_service import get_user_info

router = APIRouter()

@router.post("/add-xp")
async def add_xp(data: XPInput, request: Request):
    user_info = await get_user_info(data.user_id)
    doc = data.dict()
    doc.update({"user_name": user_info.name, "email": user_info.email})
    await request.app.mongodb["xp"].insert_one(doc)
    return {"message": "XP added"}

@router.get("/xp/{user_id}")
async def get_xp(user_id: str, request: Request):
    cursor = request.app.mongodb["xp"].find({"user_id": user_id})
    total = 0
    async for doc in cursor:
        total += doc.get("amount", 0)
    return {"user_id": user_id, "xp": total}