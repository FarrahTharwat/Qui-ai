import os
from redis import Redis

# Connect to Redis (Ensure credentials are set via environment variables!)
REDIS_HOST = os.getenv("REDIS_HOST", "qui-ai-gamify.redis.cache.windows.net")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6380))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "hUSQKm2tK2OSqNzroOM3yeKJ4VwHAhaPJAzCaGfzZPQ=")

if not REDIS_PASSWORD:
    raise ValueError("Redis password is missing. Set REDIS_PASSWORD as an environment variable.")

redis_client = Redis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD, ssl=True)

LEADERBOARD_PREFIX = "course_leaderboard:"  # Prefix for course-specific leaderboards
