from fastapi import APIRouter, HTTPException
from bson import ObjectId
from models import XPRequest
from database import xp_collection
from rules import get_xp_amount

router = APIRouter()

@router.post("/add_xp/")
async def add_xp(data: XPRequest):
    user_id = ObjectId(data.user_id)
    activity = data.activity_type.lower()

    if activity == "custom":
        if data.amount is None:
            raise HTTPException(status_code=400, detail="Custom XP amount required.")
        amount = data.amount
    else:
        amount = await get_xp_amount(activity)

    await xp_collection.update_one(
        {"user_id": user_id},
        {"$inc": {"xp": amount}},
        upsert=True
    )

    return {
        "message": f"Added {amount} XP for {activity}",
        "user_id": data.user_id,
        "xp_amount": amount
    }


