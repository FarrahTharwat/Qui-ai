from fastapi import FastAPI, HTTPException
import redis
import logging
from datetime import datetime
app = FastAPI()

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Connect to Redis
try:
    redis_client = redis.Redis(host="localhost", port=6379, decode_responses=True)
    redis_client.ping()  # Test connection
    logger.info("✅ Redis is connected")
except Exception as e:
    logger.error(f"❌ Redis connection failed: {e}")
    raise HTTPException(status_code=500, detail="Redis connection failed")

# XP Update (Increment XP Instead of Overwriting)
@app.post("/update_xp/{user_id}/{xp}")
def update_xp(user_id: int, xp: int):
    key_xp = f"user:{user_id}:xp"
    key_activity = f"user:{user_id}:last_active"

    try:
        # Check Redis connection before proceeding
        if not redis_client.ping():
            logger.error("❌ Redis is not connected")
            raise HTTPException(status_code=500, detail="Redis is not available")

        # Try incrementing XP
        redis_client.incrby(key_xp, xp)
        stored_xp = redis_client.get(key_xp)

        # Store last activity timestamp
        redis_client.set(key_activity, datetime.utcnow().timestamp())

        logger.info(f"✅ XP updated for user {user_id} | New XP: {stored_xp}")
        return {
            "message": f"XP updated for user {user_id}",
            "stored_xp": stored_xp
        }
    except redis.RedisError as redis_error:
        logger.error(f"❌ Redis operation failed: {redis_error}")
        raise HTTPException(status_code=500, detail="Redis operation failed")
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Failed to update XP")

# Get XP
@app.get("/get_xp/{user_id}")
def get_xp(user_id: int):
    key = f"user:{user_id}:xp"
    stored_xp = redis_client.get(key)

    if stored_xp:
        return {"user_id": user_id, "xp": stored_xp}
    else:
        raise HTTPException(status_code=404, detail=f"No XP found for user {user_id}")

# Streak Reset Logic for Inactive Users
@app.post("/reset_streak/{user_id}")
def reset_streak(user_id: int):
    streak_key = f"user:{user_id}:streak"
    last_active_key = f"user:{user_id}:last_active"

    last_active = redis_client.get(last_active_key)

    if last_active is None:
        redis_client.set(streak_key, 0)  # Reset streak
        return {"message": f"Streak reset for user {user_id} due to inactivity"}

    return {"message": f"User {user_id} is still active, no reset needed"}

# API Health Check
@app.get("/")
def health_check():
    return {"status": "Leaderboard API is running"}
