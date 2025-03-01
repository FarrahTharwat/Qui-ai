import datetime
import logging
import azure.functions as func
import redis

# Connect to Redis (update host if needed)
redis_client = redis.Redis(host="qui-ai-gamify.redis.cache.windows.net", port=6379, decode_responses=True)

app = func.FunctionApp()  # Create a FunctionApp instance

@app.function_name(name="StreakResetFunction")  # Function Name
@app.schedule(schedule="0 0 * * *", arg_name="mytimer", run_on_startup=True)  # Runs daily at midnight UTC
def main(mytimer: func.TimerRequest) -> None:
    logging.info("Running Streak Reset...")

    users = ["123", "456", "789"]  # Fetch dynamically in production
    for user in users:
        redis_client.set(f"user:{user}:streak", 0)
        logging.info(f"✅ Reset streak for {user}")

    logging.info("✅ Streak Reset Completed.")
