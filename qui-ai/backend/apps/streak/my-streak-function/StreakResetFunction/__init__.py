import logging
import redis
import azure.functions as func
from datetime import datetime, timezone

# Connect to Redis
try:
    redis_client = redis.Redis(host="qui-ai-gamify.redis.cache.windows.net", port=6379, decode_responses=True)
    redis_client.ping()  # Check if Redis is reachable
    logging.info("✅ Connected to Redis successfully!")
except Exception as e:
    logging.error(f"❌ Redis connection failed: {e}")
    redis_client = None  # Prevent execution if Redis is down

def reset_streaks():
    """Resets the streak for users who have been inactive for over 24 hours."""
    if not redis_client:
        logging.error("❌ Skipping streak reset: Redis is not connected.")
        return

    now = datetime.now(timezone.utc).timestamp()
    inactive_threshold = now - (24 * 60 * 60)  # 24 hours ago

    try:
        keys = redis_client.keys("user:*:last_active")
        if not keys:
            logging.info("✅ No inactive users found. Skipping reset.")
            return

        for key in keys:
            user_id = key.split(":")[1]  # Extract user ID
            last_active = redis_client.get(key)

            if last_active is None:
                logging.warning(f"⚠️ Skipping user {user_id}: No last active timestamp found.")
                continue

            try:
                last_active = float(last_active)
            except ValueError:
                logging.warning(f"⚠️ Invalid timestamp format for user {user_id}. Skipping...")
                continue

            if last_active < inactive_threshold:
                streak_key = f"user:{user_id}:streak"
                redis_client.set(streak_key, 0)  # Reset streak
                logging.info(f"🔴 Streak reset for user {user_id}")

    except Exception as e:
        logging.error(f"❌ Error during streak reset: {e}")

# Azure Function entry point
def main(mytimer: func.TimerRequest) -> None:
    logging.info("⏳ Running Streak Reset Task...")
    reset_streaks()
    logging.info("✅ Streak Reset Task Completed.")
