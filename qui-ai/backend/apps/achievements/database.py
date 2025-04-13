from pymongo import MongoClient
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URI = "mongodb+srv://Fatma:Kiqvez-sikpu6-dargez@track-progress.mongocluster.cosmos.azure.com/?tls=true&authMechanism=SCRAM-SHA-256&retrywrites=false&maxIdleTimeMS=120000"
client = AsyncIOMotorClient(MONGO_URI)
db = client["achievements-DB"]
achievements_collection = db["achievements"]
user_achievements_collection = db["user_achievements"]
