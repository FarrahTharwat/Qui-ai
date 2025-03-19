import os
import asyncio
import httpx
import subprocess
from redis import Redis
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List
from models import Leaderboard, Base

# Load environment variables
load_dotenv()

# Secure Redis connection
REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6380))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")

if not REDIS_PASSWORD:
    raise ValueError("Redis password is missing. Set REDIS_PASSWORD as an environment variable.")

redis_client = Redis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD, ssl=True)

LEADERBOARD_PREFIX = "course_leaderboard:"
TRACKING_SERVICE_URL = os.getenv("TRACKING_SERVICE_URL")

# Secure PostgreSQL connection
command = "az account get-access-token --resource https://ossrdbms-aad.database.windows.net --query accessToken --output tsv"
PGPASSWORD = subprocess.getoutput(command).strip()

DATABASE_URL = (
    f"postgresql+asyncpg://{os.getenv('PGUSER')}:{PGPASSWORD}@{os.getenv('PGHOST')}:{os.getenv('PGPORT')}/{os.getenv('PGDATABASE')}"
)

engine = create_async_engine(DATABASE_URL, echo=True)
async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db():
    async with async_session_maker() as session:
        yield session

# Background Task to Sync Redis with PostgreSQL
async def sync_redis_with_postgresql():
    while True:
        async with async_session_maker() as db:
            result = await db.execute(select(Leaderboard))
            entries = result.scalars().all()
            with redis_client.pipeline() as pipe:
                for entry in entries:
                    leaderboard_key = f"{LEADERBOARD_PREFIX}{entry.course_id}"
                    pipe.zadd(leaderboard_key, {entry.username: entry.score})
                pipe.execute()
        await asyncio.sleep(300)  # Sync every 5 minutes

# FastAPI app
app = FastAPI()
router = APIRouter()



@app.get("/")
def read_root():
    return {"message": "Welcome to the API"}

@router.on_event("startup")
async def start_sync_task():
    asyncio.create_task(sync_redis_with_postgresql())

# Pydantic Model
class LeaderboardEntry(BaseModel):
    course_id: str
    username: str
    score: int

@router.post("/submit_score/")
async def submit_score(entry: LeaderboardEntry, db: AsyncSession = Depends(get_db)):
    leaderboard_key = f"{LEADERBOARD_PREFIX}{entry.course_id}"
    if entry.score < 0:
        raise HTTPException(status_code=400, detail="Score must be a positive integer.")
    result = await db.execute(select(Leaderboard).where(
        (Leaderboard.course_id == entry.course_id) & (Leaderboard.username == entry.username)
    ))
    existing_entry = result.scalars().first()
    if existing_entry:
        existing_entry.score = max(existing_entry.score, entry.score)
    else:
        new_entry = Leaderboard(course_id=entry.course_id, username=entry.username, score=entry.score)
        db.add(new_entry)
    await db.commit()
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
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(TRACKING_SERVICE_URL)
            response.raise_for_status()
            scores = response.json()
            return await update_leaderboard(scores)
    except httpx.HTTPError as e:
        raise HTTPException(status_code=500, detail=f"Error fetching scores: {str(e)}")

async def update_leaderboard(scores):
    async with async_session_maker() as db:
        for score_entry in scores:
            username = score_entry["username"]
            course_id = score_entry["course_id"]
            score = score_entry["score"]
            result = await db.execute(select(Leaderboard).where(
                (Leaderboard.course_id == course_id) & (Leaderboard.username == username)
            ))
            existing_entry = result.scalars().first()
            if existing_entry:
                existing_entry.score = max(existing_entry.score, score)
            else:
                db.add(Leaderboard(course_id=course_id, username=username, score=score))
        await db.commit()
    return {"message": "Leaderboard updated successfully."}

@router.delete("/reset/{course_id}")
async def reset_leaderboard(course_id: str):
    leaderboard_key = f"{LEADERBOARD_PREFIX}{course_id}"
    if not redis_client.exists(leaderboard_key):
        raise HTTPException(status_code=404, detail="Leaderboard not found.")
    redis_client.delete(leaderboard_key)
    return {"message": f"Leaderboard for course {course_id} reset!"}

app.include_router(router)

