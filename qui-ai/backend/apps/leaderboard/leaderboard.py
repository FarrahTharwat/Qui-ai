from fastapi import FastAPI, HTTPException, Depends
from redis import Redis
import httpx
import os
from pydantic import BaseModel
from typing import List

app = FastAPI()

# Connect to Redis (Ensure credentials are set via environment variables!)
REDIS_HOST = os.getenv("REDIS_HOST", "qui-ai-gamify.redis.cache.windows.net")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6380))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "hUSQKm2tK2OSqNzroOM3yeKJ4VwHAhaPJAzCaGfzZPQ=")
if not REDIS_PASSWORD:
    raise ValueError("Redis password is missing. Set REDIS_PASSWORD as an environment variable.")

redis_client = Redis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD, ssl=True)

LEADERBOARD_PREFIX = "course_leaderboard:"  # Prefix for course-specific leaderboards
TRACKING_SERVICE_URL = os.getenv("TRACKING_SERVICE_URL", "https://your-tracking-service.com/api/scores")


# Define Pydantic Model
class LeaderboardEntry(BaseModel):
    course_id: str
    username: str
    score: int


# 🚀 Submit a score for a user in a specific course
@app.post("/submit_score/")
async def submit_score(entry: LeaderboardEntry):
    leaderboard_key = f"{LEADERBOARD_PREFIX}{entry.course_id}"

    # Ensure valid score input
    if entry.score < 0:
        raise HTTPException(status_code=400, detail="Score must be a positive integer.")

    redis_client.zadd(leaderboard_key, {entry.username: entry.score})
    return {"message": f"Score {entry.score} submitted for {entry.username} in course {entry.course_id}"}


# 🏆 Get a user's rank and score in a specific course
@app.get("/rank/{course_id}/{username}")
async def get_user_rank(course_id: str, username: str):
    leaderboard_key = f"{LEADERBOARD_PREFIX}{course_id}"

    # Fetch score and rank atomically
    with redis_client.pipeline() as pipe:
        pipe.zscore(leaderboard_key, username)
        pipe.zrevrank(leaderboard_key, username)
        score, rank = pipe.execute()

    if score is None or rank is None:
        raise HTTPException(status_code=404, detail="User not found in this course")

    return {"username": username, "course_id": course_id, "rank": rank + 1, "score": score}


# 🚀 Submit multiple leaderboard scores in bulk
@app.post("/update_leaderboard/")
async def update_leaderboard(scores: List[LeaderboardEntry]):
    if not scores:
        raise HTTPException(status_code=400, detail="No scores provided.")

    with redis_client.pipeline() as pipe:
        for entry in scores:
            leaderboard_key = f"{LEADERBOARD_PREFIX}{entry.course_id}"
            pipe.zadd(leaderboard_key, {entry.username: entry.score})
        pipe.execute()

    return {"message": "Leaderboard updated successfully!"}


# 🔄 Fetch scores from external Tracking Service and update leaderboard
@app.post("/fetch_and_update_leaderboard/")
async def fetch_and_update_leaderboard():
    async with httpx.AsyncClient() as client:
        response = await client.get(TRACKING_SERVICE_URL)
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="Failed to fetch scores from tracking service.")

        scores = response.json()
        return await update_leaderboard(scores)  # Reuse bulk update function


# 🎯 Get the top N players in a specific course
@app.get("/top/{course_id}/{count}")
async def get_top_players(course_id: str, count: int):
    if count <= 0:
        raise HTTPException(status_code=400, detail="Count must be a positive integer.")

    leaderboard_key = f"{LEADERBOARD_PREFIX}{course_id}"
    top_players = redis_client.zrevrange(leaderboard_key, 0, count - 1, withscores=True)

    if not top_players:
        raise HTTPException(status_code=404, detail="No players found for this course.")

    return [{"rank": idx + 1, "username": player[0], "score": player[1]} for idx, player in enumerate(top_players)]


# 🔄 Reset the leaderboard for a specific course
@app.delete("/reset/{course_id}")
async def reset_leaderboard(course_id: str):
    leaderboard_key = f"{LEADERBOARD_PREFIX}{course_id}"
    if not redis_client.exists(leaderboard_key):
        raise HTTPException(status_code=404, detail="Leaderboard not found.")

    redis_client.delete(leaderboard_key)
    return {"message": f"Leaderboard for course {course_id} reset!"}
