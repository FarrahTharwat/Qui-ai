from fastapi import APIRouter, HTTPException
from xp_points.models import XPRequest
from xp_points.appwrite_client import databases
from appwrite.exception import AppwriteException
import os, uuid, requests

router = APIRouter()

# XP rules per activity type
XP_RULES = {
    "lesson": 10,
    "quiz": 20,
    "streak": 5
}

@router.post("/add_xp")
def add_xp(data: XPRequest):
    if data.status != "completed":
        return {"message": "XP not awarded (status not completed)."}

    xp = XP_RULES.get(data.activity_type, 0)

    try:
        # ✅ Create XP document in Appwrite
        databases.create_document(
            database_id=os.getenv("APPWRITE_DB"),
            collection_id=os.getenv("XP_COLLECTION"),
            document_id=str(uuid.uuid4()),
            data={
                "user_id": data.user_id,
                "xp_value": xp,
                "activity_type": data.activity_type,
                "activity_id": data.activity_id,
                "status": data.status
            }
        )
    except AppwriteException as e:
        raise HTTPException(status_code=500, detail=f"Appwrite error: {str(e)}")

    # ✅ Notify achievement service after awarding XP
    try:
        res = requests.post(
            f"{os.getenv('ACHIEVEMENT_URL')}/check",
            json={"user_id": data.user_id},
            timeout=3  # Prevent hanging requests
        )
        if res.status_code == 200:
            print(f"✅ Achievement notified for {data.user_id}")
        else:
            print(f"⚠️ Achievement service returned {res.status_code}: {res.text}")
    except Exception as e:
        print(f"⚠️ Notify achievement failed: {str(e)}")

    return {"message": f"{xp} XP awarded to user {data.user_id}"}

