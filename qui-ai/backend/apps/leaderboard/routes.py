import asyncio
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import FastAPI, APIRouter, HTTPException, Depends
from database import (redis_client, LEADERBOARD_PREFIX, TRACKING_SERVICE_URL, get_db, sync_redis_with_postgresql)
from models import Leaderboard, LeaderboardEntry
from typing import List
from worker import update_leaderboard

# FastAPI app
app = FastAPI()
router = APIRouter()

@app.get("/")
def read_root():
    return {"message": "Welcome to the API"}

@router.on_event("startup")
async def start_sync_task():
    asyncio.create_task(sync_redis_with_postgresql())  # Remove process_updates() call


@router.post("/submit_score/")
async def submit_scores(entries: List[LeaderboardEntry], db: AsyncSession = Depends(get_db)):
    try:
        for entry in entries:
            new_entry = Leaderboard(
                course_id=entry.course_id,
                username=entry.username,
                score=entry.score
            )
            db.add(new_entry)
        await db.commit()
        return {"message": "Scores submitted successfully!"}
    except Exception as e:
        await db.rollback()
        return {"error": str(e)}


@router.get("/rank/{course_id}/{username}")
async def get_user_rank(course_id: str, username: str):
    leaderboard_key = f"{LEADERBOARD_PREFIX}{course_id}"
    with redis_client.pipeline() as pipe:
        pipe.zscore(leaderboard_key, username)
        pipe.zrevrank(leaderboard_key, username)
        score, rank = pipe.execute()
    if score is None or rank is None:
        raise HTTPException(status_code=404, detail="User not found in this course")
    return {"username": username, "course_id": course_id, "rank": rank + 1, "score": score}

@router.get("/top/{course_id}/{count}")
async def get_top_players(course_id: str, count: int, db: AsyncSession = Depends(get_db)):
    if count <= 0:
        raise HTTPException(status_code=400, detail="Count must be a positive integer.")
    leaderboard_key = f"{LEADERBOARD_PREFIX}{course_id}"
    top_players = redis_client.zrevrange(leaderboard_key, 0, count - 1, withscores=True)
    if top_players:
        return [{"rank": idx + 1, "username": player[0].decode(), "score": player[1]} for idx, player in enumerate(top_players)]
    result = await db.execute(
        select(Leaderboard).where(Leaderboard.course_id == course_id).order_by(Leaderboard.score.desc()).limit(count)
    )
    top_players = result.scalars().all()
    if not top_players:
        raise HTTPException(status_code=404, detail="No players found for this course.")
    return [{"rank": idx + 1, "username": player.username, "score": player.score} for idx, player in enumerate(top_players)]


@router.post("/fetch_and_update_leaderboard/")
async def fetch_and_update_leaderboard():
    """
    Fetch latest scores and trigger leaderboard update via Celery.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(TRACKING_SERVICE_URL)
            response.raise_for_status()
            scores = response.json()

        # Call Celery task asynchronously
        task = update_leaderboard.delay(scores)
        return {"message": "Leaderboard update in progress", "task_id": task.id}

    except httpx.HTTPError as e:
        raise HTTPException(status_code=500, detail=f"Error fetching scores: {str(e)}")
@router.delete("/reset/{course_id}")
async def reset_leaderboard(course_id: str):
    leaderboard_key = f"{LEADERBOARD_PREFIX}{course_id}"
    if not redis_client.exists(leaderboard_key):
        raise HTTPException(status_code=404, detail="Leaderboard not found.")
    redis_client.delete(leaderboard_key)
    return {"message": f"Leaderboard for course {course_id} reset!"}
