from fastapi import APIRouter, Request
from models.progress_input import ProgressInput

router = APIRouter()

@router.post("/track")
async def track(data: ProgressInput, request: Request):
    await request.app.mongodb["progress"].insert_one(data.dict())
    return {"message": "Progress saved"}