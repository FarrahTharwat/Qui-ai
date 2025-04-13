from database import tracking_rules_collection
from fastapi import HTTPException

async def is_tracking_allowed(activity_type: str) -> bool:
    rule = await tracking_rules_collection.find_one({"activity_type": activity_type.lower()})
    if not rule or not rule.get("enabled", False):
        raise HTTPException(status_code=403, detail=f"Tracking not allowed for '{activity_type}'")
    return True