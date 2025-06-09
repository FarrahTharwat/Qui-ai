import motor.motor_asyncio
import os

db_url = os.getenv("MONGO_URL")
client = motor.motor_asyncio.AsyncIOMotorClient(db_url)
db = client["track_progress_db"]