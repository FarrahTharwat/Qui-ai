import motor.motor_asyncio
import os
from dotenv import load_dotenv
load_dotenv()

db_url = os.getenv("MONGO_URL")
client = motor.motor_asyncio.AsyncIOMotorClient(db_url)
db = client["xp_db"]