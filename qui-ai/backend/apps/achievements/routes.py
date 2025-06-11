from fastapi import APIRouter, HTTPException
from achievements.models import AchievementRequest
from achievements.appwrite_client import databases
from appwrite.query import Query
from appwrite.exception import AppwriteException
from datetime import datetime
import os, uuid, requests

router = APIRouter()

def make_appwrite_headers():
    return {
        "X-Appwrite-Project": os.getenv("APPWRITE_PROJECT_ID"),
        "X-Appwrite-Key": os.getenv("APPWRITE_API_KEY"),
        "Content-Type": "application/json"
    }

@router.post("/check")
def check_achievements(request: AchievementRequest):
    try:
        # 1. Fetch all XP documents for the user using filters
        params = {
            "filters[user_id]": request.user_id
        }
        
        xp_res = requests.get(
            f"{os.getenv('APPWRITE_ENDPOINT')}/databases/{os.getenv('APPWRITE_DB')}/collections/{os.getenv('XP_COLLECTION')}/documents",
            headers=make_appwrite_headers(),
            params=params,
            timeout=5
        )
        
        if xp_res.status_code != 200:
            return {"error": f"Failed to fetch XP: {xp_res.status_code} {xp_res.text}"}
        
        xp_docs = xp_res.json().get("documents", [])
        total_xp = sum(int(doc.get("xp_value", 0)) for doc in xp_docs)
        unlocked = []
        
        if total_xp >= 50:
            unlocked.append("XP Master")
        
        # 2. Process each unlocked achievement
        for title in unlocked:
            # Check if achievement already exists using filters
            check_params = {
                "filters[user_id]": request.user_id,
                "filters[achievement]": title
            }
            
            check_res = requests.get(
                f"{os.getenv('APPWRITE_ENDPOINT')}/databases/{os.getenv('APPWRITE_DB')}/collections/{os.getenv('ACHIEVEMENTS_COLLECTION')}/documents",
                headers=make_appwrite_headers(),
                params=check_params,
                timeout=5
            )
            
            if check_res.status_code != 200:
                continue  # Skip on error
            
            existing = check_res.json().get("documents", [])
            if not existing:
                # Create new achievement
                create_res = requests.post(
                    f"{os.getenv('APPWRITE_ENDPOINT')}/databases/{os.getenv('APPWRITE_DB')}/collections/{os.getenv('ACHIEVEMENTS_COLLECTION')}/documents",
                    headers=make_appwrite_headers(),
                    json={
                        "documentId": str(uuid.uuid4()),
                        "data": {
                            "user_id": request.user_id,
                            "achievement": title,
                            "timestamp": datetime.utcnow().isoformat() + "Z"
                        }
                    },
                    timeout=5
                )
                if create_res.status_code not in (200, 201):
                    print(f"Failed to create achievement: {create_res.text}")
        
        return {"unlocked": unlocked}

    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="Appwrite request timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")