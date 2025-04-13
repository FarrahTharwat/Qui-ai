from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Any
from rules import check_and_award_achievements

router = APIRouter()

class DynamicUserStats(BaseModel):
    user_id: str
    data: Dict[str, Any]  # This allows any custom stats to be passed

@router.post("/check_achievements")
async def check_achievements(payload: DynamicUserStats):
    awarded = await check_and_award_achievements(payload.user_id, payload.data)
    return {"new_achievements": awarded}
