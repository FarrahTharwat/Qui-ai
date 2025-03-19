import os
import asyncio
import subprocess
from redis import Redis
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
from dotenv import load_dotenv
from models import Leaderboard
from models import Base  # Import Base model

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


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)  # Ensures tables are created
