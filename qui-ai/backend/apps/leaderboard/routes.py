from fastapi import APIRouter, HTTPException
from typing import List
import httpx
from database import redis_client, LEADERBOARD_PREFIX
from models import LeaderboardEntry
import os

router = APIRouter()
TRACKING_SERVICE_URL = os.getenv("TRACKING_SERVICE_URL", "https://your-tracking-service.com/api/scores")

@router.post("/submit_score/")
async def submit_score(entry: LeaderboardEntry):
    leaderboard_key = f"{LEADERBOARD_PREFIX}{entry.course_id}"
    if entry.score < 0:
        raise HTTPException(status_code=400, detail="Score must be a positive integer.")
    redis_client.zadd(leaderboard_key, {entry.username: entry.score})
    return {"message": f"Score {entry.score} submitted for {entry.username} in course {entry.course_id}"}

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

@router.post("/update_leaderboard/")
async def update_leaderboard(scores: List[LeaderboardEntry]):
    if not scores:
        raise HTTPException(status_code=400, detail="No scores provided.")
    with redis_client.pipeline() as pipe:
        for entry in scores:
            leaderboard_key = f"{LEADERBOARD_PREFIX}{entry.course_id}"
            pipe.zadd(leaderboard_key, {entry.username: entry.score})
        pipe.execute()
    return {"message": "Leaderboard updated successfully!"}

@router.post("/fetch_and_update_leaderboard/")
async def fetch_and_update_leaderboard():
    async with httpx.AsyncClient() as client:
        response = await client.get(TRACKING_SERVICE_URL)
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="Failed to fetch scores from tracking service.")
        scores = response.json()
        return await update_leaderboard(scores)

@router.get("/top/{course_id}")
async def get_top_players(course_id: str):
    leaderboard_key = f"{LEADERBOARD_PREFIX}{course_id}"
    top_players = redis_client.zrevrange(leaderboard_key, 0, 9, withscores=True)  # Always fetch top 10

    if not top_players:
        raise HTTPException(status_code=404, detail="No players found for this course.")

    return [{"rank": idx + 1, "username": player[0], "score": player[1]} for idx, player in enumerate(top_players)]

@router.delete("/reset/{course_id}")
async def reset_leaderboard(course_id: str):
    leaderboard_key = f"{LEADERBOARD_PREFIX}{course_id}"
    if not redis_client.exists(leaderboard_key):
        raise HTTPException(status_code=404, detail="Leaderboard not found.")
    redis_client.delete(leaderboard_key)
    return {"message": f"Leaderboard for course {course_id} reset!"}