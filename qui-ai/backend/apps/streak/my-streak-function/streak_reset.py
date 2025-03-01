import time
from datetime import datetime, timezone
import redis

redis_client = redis.Redis(host="localhost", port=6379, decode_responses=True)

def reset_streaks():
    now = datetime.now(timezone.utc).timestamp()
    inactive_threshold = now - (24 * 60 * 60)  # 24 hours ago

    # Get all users
    for key in redis_client.keys("user:*:last_active"):
        user_id = key.split(":")[1]  # Extract user ID
        last_active = float(redis_client.get(key))

        if last_active < inactive_threshold:
            streak_key = f"user:{user_id}:streak"
            redis_client.set(streak_key, 0)  # Reset streak
            print(f"🔥 Streak reset for user {user_id}")

if __name__ == "__main__":
    while True:
        reset_streaks()
        print("✅ Streak check completed. Sleeping for 24 hours...")
        time.sleep(24 * 60 * 60)  # Sleep for 24 hours
