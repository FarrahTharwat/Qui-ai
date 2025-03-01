import redis

try:
    redis_client = redis.Redis(host="localhost", port=6379, decode_responses=True)
    redis_client.ping()
    print("✅ Redis is working")
except Exception as e:
    print(f"❌ Redis connection failed: {e}")
