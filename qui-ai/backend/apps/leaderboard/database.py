import os
import asyncio
import subprocess
import redis
import warnings
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
from dotenv import load_dotenv
from models import Leaderboard

warnings.filterwarnings("ignore", message="ssl_cert_reqs is set to CERT_NONE")

load_dotenv()

# Constants
LEADERBOARD_PREFIX = "course_leaderboard:"
TRACKING_SERVICE_URL = os.getenv("TRACKING_SERVICE_URL")

# Redis Configuration
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST"),
    port=int(os.getenv("REDIS_PORT", 6380)),
    password=os.getenv("REDIS_PASSWORD"),
    ssl=True,
    ssl_cert_reqs=None,
    decode_responses=True
)

# PostgreSQL Initialization
async def get_azure_token():
    try:
        result = subprocess.run(
            ["az", "account", "get-access-token", "--resource",
             "https://ossrdbms-aad.database.windows.net", "--query", "accessToken", "-o", "tsv"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Azure CLI error: {e.stderr}") from e

engine = None
async_session_maker = None

async def initialize_db():
    global engine, async_session_maker
    access_token = await get_azure_token()
    DATABASE_URL = f"postgresql+asyncpg://{os.getenv('POSTGRES_USER')}:{access_token}@{os.getenv('POSTGRES_HOST')}:5432/{os.getenv('POSTGRES_DB')}?sslmode=require"
    engine = create_async_engine(DATABASE_URL, echo=True)
    async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db():
    if not async_session_maker:
        await initialize_db()
    async with async_session_maker() as session:
        yield session

async def sync_redis_with_postgresql():
    while True:
        try:
            async with async_session_maker() as db:
                result = await db.execute(select(Leaderboard))
                for entry in result.scalars():
                    redis_client.zadd(f"{LEADERBOARD_PREFIX}{entry.course_id}", {entry.username: entry.score})
            await asyncio.sleep(300)
        except Exception as e:
            print(f"Sync error: {e}")
            await asyncio.sleep(60)