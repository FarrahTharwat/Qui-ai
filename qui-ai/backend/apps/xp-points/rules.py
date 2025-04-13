from database import xp_rules_collection
from fastapi import HTTPException

async def get_xp_amount(activity_type: str) -> int:
    rule = await xp_rules_collection.find_one({"activity_type": activity_type.lower()})
    if not rule or "amount" not in rule:
        raise HTTPException(status_code=404, detail=f"No XP rule found for '{activity_type}'")
    return rule["amount"]
