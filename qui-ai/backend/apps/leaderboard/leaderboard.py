from fastapi import FastAPI, HTTPException, Depends
from redis import Redis
import httpx
import os
import requests

app = FastAPI()

# Connect to Redis (Update host and port if using Azure Redis!)
REDIS_HOST = os.getenv("REDIS_HOST", "qui-ai-gamify.redis.cache.windows.net")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "hUSQKm2tK2OSqNzroOM3yeKJ4VwHAhaPJAzCaGfzZPQ=")
redis_client = Redis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD, decode_responses=True)

LEADERBOARD_PREFIX = "course_leaderboard:"  # Prefix for course-specific leaderboards
TRACKING_SERVICE_URL = "https://your-tracking-service.com/api/scores"
# 🚀 Submit a score for a user in a specific course
@app.post("/submit_score/")
async def submit_score(course_id: str, username: str, score: int):
    leaderboard_key = f"{LEADERBOARD_PREFIX}{course_id}"
    redis_client.zadd(leaderboard_key, {username: score})
    return {"message": f"Score {score} submitted for {username} in course {course_id}"}


# 🏆 Get a user's rank and score in a specific course
@app.get("/rank/{course_id}/{username}")
async def get_user_rank(course_id: str, username: str):
    leaderboard_key = f"{LEADERBOARD_PREFIX}{course_id}"
    score = redis_client.zscore(leaderboard_key, username)
    if score is None:
        raise HTTPException(status_code=404, detail="User not found in this course")

    rank = redis_client.zrevrank(leaderboard_key, username)
    if rank is None:
        raise HTTPException(status_code=404, detail="User not ranked in this course")

    return {"username": username, "course_id": course_id, "rank": rank + 1, "score": score}


# 🚀 Submit a score dynamically from tracking service
@app.post("/update_leaderboard/")
async def update_leaderboard():
    async with httpx.AsyncClient() as client:
        response = await client.get(TRACKING_SERVICE_URL)
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="Failed to fetch scores from tracking service")

        scores = response.json()
        for entry in scores:
            course_id = entry["course_id"]
            username = entry["username"]
            score = entry["score"]
            leaderboard_key = f"{LEADERBOARD_PREFIX}{course_id}"
            redis_client.zadd(leaderboard_key, {username: score})

    return {"message": "Leaderboard updated from tracking service"}


# 🎯 Get the top N players in a specific course
@app.get("/top/{course_id}/{count}")
async def get_top_players(course_id: str, count: int):
    leaderboard_key = f"{LEADERBOARD_PREFIX}{course_id}"
    top_players = redis_client.zrevrange(leaderboard_key, 0, count - 1, withscores=True)
    return [{"rank": idx + 1, "username": player[0], "score": player[1]} for idx, player in enumerate(top_players)]


# 🔄 Reset the leaderboard for a specific course
@app.delete("/reset/{course_id}")
async def reset_leaderboard(course_id: str):
    leaderboard_key = f"{LEADERBOARD_PREFIX}{course_id}"
    redis_client.delete(leaderboard_key)
    return {"message": f"Leaderboard for course {course_id} reset!"}
