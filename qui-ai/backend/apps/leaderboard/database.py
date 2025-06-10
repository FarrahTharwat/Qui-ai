import os
import asyncio
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

# Redis Configuration - using Redis Cloud or local Redis
redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "localhost"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    password=os.getenv("REDIS_PASSWORD"),
    ssl=os.getenv("REDIS_SSL", "false").lower() == "true",
    ssl_cert_reqs=None if os.getenv("REDIS_SSL", "false").lower() == "true" else None,
    decode_responses=True
)


# Supabase PostgreSQL Configuration
def get_database_url():
    """Build Supabase database URL from environment variables"""
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")  # Service role key for server-side

    # Alternative: Direct database connection
    if os.getenv("DATABASE_URL"):
        return os.getenv("DATABASE_URL")

    # Build from individual components
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD")
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "postgres")

    if not all([db_password, db_host]):
        raise ValueError("Missing required database connection parameters. Set DATABASE_URL or DB_HOST, DB_PASSWORD")

    return f"postgresql+asyncpg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}?sslmode=require"


engine = None
async_session_maker = None


async def initialize_db():
    """Initialize database connection"""
    global engine, async_session_maker

    database_url = get_database_url()
    engine = create_async_engine(
        database_url,
        echo=os.getenv("SQL_ECHO", "false").lower() == "true",
        pool_size=10,
        max_overflow=20
    )
    async_session_maker = sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )


async def get_db():
    """Database dependency for FastAPI"""
    if not async_session_maker:
        await initialize_db()
    async with async_session_maker() as session:
        yield session


async def sync_redis_with_postgresql():
    """Background task to sync PostgreSQL data to Redis"""
    while True:
        try:
            if not async_session_maker:
                await initialize_db()

            async with async_session_maker() as db:
                result = await db.execute(select(Leaderboard))
                entries = result.scalars().all()

                # Use pipeline for efficient Redis operations
                with redis_client.pipeline() as pipe:
                    for entry in entries:
                        redis_key = f"{LEADERBOARD_PREFIX}{entry.course_id}"
                        pipe.zadd(redis_key, {entry.username: entry.score})
                    pipe.execute()

                print(f"Synced {len(entries)} leaderboard entries to Redis")

        except Exception as e:
            print(f"Sync error: {e}")
            await asyncio.sleep(60)  # Wait before retrying on error
            continue

        await asyncio.sleep(300)  # Sync every 5 minutes


async def test_connections():
    """Test both database and Redis connections"""
    try:
        # Test database connection
        await initialize_db()
        async with async_session_maker() as db:
            await db.execute(select(1))
        print("✅ Database connection successful")

        # Test Redis connection
        redis_client.ping()
        print("✅ Redis connection successful")

    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        raise