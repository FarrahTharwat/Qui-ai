from fastapi import APIRouter, HTTPException
from track_progress.models import Progress
from track_progress.appwrite_client import databases
from appwrite.exception import AppwriteException
import os, uuid, requests

router = APIRouter()

@router.post("/track")
def track_progress(progress: Progress):
    data = progress.dict()
    
    try:
        # Store progress in Appwrite
        databases.create_document(
            database_id=os.getenv("APPWRITE_DB"),
            collection_id=os.getenv("APPWRITE_COLLECTION"),
            document_id=str(uuid.uuid4()),
            data=data
        )
    except AppwriteException as e:
        raise HTTPException(status_code=500, detail=f"Appwrite error: {str(e)}")

    # Forward to XP service if completed
    if progress.status == "completed":
        try:
            res = requests.post(f"{os.getenv('XP_SERVICE_URL')}/add_xp", json=data)
            if not res.ok:
                raise HTTPException(status_code=res.status_code, detail="XP service failed")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"XP service error: {str(e)}")

    return {"message": "Tracked successfully"}
