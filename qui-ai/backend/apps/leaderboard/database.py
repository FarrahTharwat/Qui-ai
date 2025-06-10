# Fixed database.py - Resolved asyncpg prepared statement issue
import os
import asyncio
import redis
import warnings
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
from dotenv import load_dotenv, find_dotenv
from models import Leaderboard

warnings.filterwarnings("ignore", message="ssl_cert_reqs is set to CERT_NONE")


def load_environment():
    """Load environment variables with multiple fallback strategies"""
    print("=== LOADING ENVIRONMENT VARIABLES ===")

    # Get the current working directory
    current_dir = Path.cwd()
    print(f"Current directory: {current_dir}")

    # List of possible .env file locations
    env_paths = [
        current_dir / ".env",
        current_dir.parent / ".env",
        current_dir.parent.parent / ".env",
        Path(__file__).parent / ".env",
        Path(__file__).parent.parent / ".env",
    ]

    env_loaded = False

    # Try each possible location
    for env_path in env_paths:
        if env_path.exists():
            print(f"Found .env file at: {env_path}")
            result = load_dotenv(env_path, verbose=True, override=True)
            print(f"Load result: {result}")
            if result:
                env_loaded = True
                break

    if not env_loaded:
        # Try using find_dotenv as fallback
        env_file = find_dotenv()
        if env_file:
            print(f"Found .env file using find_dotenv: {env_file}")
            load_dotenv(env_file, verbose=True, override=True)
            env_loaded = True

    if not env_loaded:
        print("WARNING: No .env file found! Using system environment variables only.")

    # Print loaded environment variables (masked for security)
    print("\n=== ENVIRONMENT VARIABLES STATUS ===")
    required_vars = [
        "DATABASE_URL", "DB_PASSWORD", "DB_HOST", "DB_USER", "DB_NAME",
        "REDIS_HOST", "REDIS_PASSWORD", "REDIS_PORT", "REDIS_URL"
    ]

    for var in required_vars:
        value = os.getenv(var)
        if value:
            if "PASSWORD" in var or "URL" in var:
                masked = value[:8] + "..." + value[-4:] if len(value) > 12 else "***"
                print(f"✅ {var}: {masked}")
            else:
                print(f"✅ {var}: {value}")
        else:
            print(f"❌ {var}: NOT SET")

    print("=== END ENVIRONMENT LOADING ===\n")


# Load environment variables first
load_environment()

# Constants
LEADERBOARD_PREFIX = "course_leaderboard:"
TRACKING_SERVICE_URL = os.getenv("TRACKING_SERVICE_URL")


def create_redis_client():
    """Create Redis client - Updated with working configuration"""
    print("=== CONFIGURING REDIS CONNECTION ===")

    # Get Redis connection parameters
    redis_host = os.getenv("REDIS_HOST")
    redis_port = int(os.getenv("REDIS_PORT", 6379))
    redis_password = os.getenv("REDIS_PASSWORD")
    redis_username = os.getenv("REDIS_USERNAME", "default")
    redis_ssl = os.getenv("REDIS_SSL", "false").lower() == "true"

    print(f"REDIS_HOST: {redis_host}")
    print(f"REDIS_PORT: {redis_port}")
    print(f"REDIS_USERNAME: {redis_username}")
    print(f"REDIS_PASSWORD: {'***' if redis_password else 'Not set'}")
    print(f"REDIS_SSL: {redis_ssl}")

    if not redis_host or not redis_password:
        error_msg = "Redis connection parameters missing!"
        print(f"❌ {error_msg}")
        raise ValueError(error_msg)

    # Method 1: Try Redis URL (non-SSL since that's what works)
    redis_url = os.getenv("REDIS_URL")
    if redis_url and not redis_ssl:
        print(f"Attempting connection with REDIS_URL (non-SSL): {redis_url[:30]}...")
        try:
            client = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=30,
                socket_timeout=30,
                retry_on_timeout=True,
                health_check_interval=30
            )
            result = client.ping()
            print(f"✅ Redis connection successful (URL method): {result}")
            return client
        except Exception as e:
            print(f"❌ Redis URL connection failed: {e}")

    # Method 2: Individual parameters (non-SSL)
    print("Attempting connection with individual parameters (non-SSL)...")
    try:
        client = redis.Redis(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            decode_responses=True,
            ssl=False,  # Explicitly set to False since SSL doesn't work
            socket_connect_timeout=30,
            socket_timeout=30,
            retry_on_timeout=True,
            health_check_interval=30
        )
        result = client.ping()
        print(f"✅ Redis connection successful (parameter method): {result}")
        return client
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        print("\n💡 TROUBLESHOOTING:")
        print("1. Check your Redis Cloud credentials")
        print("2. Verify your internet connection")
        print("3. Ensure Redis Cloud instance is running")
        print("4. Check firewall settings")
        raise


# Create Redis client
redis_client = create_redis_client()


def get_database_url():
    """Build database URL from environment variables - Fixed for asyncpg"""
    print("=== CONFIGURING DATABASE CONNECTION ===")

    # Method 1: Direct DATABASE_URL (preferred)
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        print("✅ Using DATABASE_URL from environment")

        # Convert postgres:// to postgresql+asyncpg:// if needed
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
            print("🔄 Converted postgres:// to postgresql+asyncpg://")
        elif database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
            print("🔄 Converted postgresql:// to postgresql+asyncpg://")

        # Remove sslmode parameter if present (asyncpg doesn't support it)
        if "sslmode=" in database_url:
            # Split URL and parameters
            if "?" in database_url:
                base_url, params = database_url.split("?", 1)
                # Remove sslmode parameter
                param_pairs = []
                for param in params.split("&"):
                    if not param.startswith("sslmode="):
                        param_pairs.append(param)

                # Reconstruct URL
                if param_pairs:
                    database_url = f"{base_url}?{'&'.join(param_pairs)}"
                else:
                    database_url = base_url

                print("🔄 Removed sslmode parameter (not supported by asyncpg)")

        return database_url

    # Method 2: Build from individual components
    print("DATABASE_URL not found, building from components...")

    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD")
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "postgres")

    print(f"DB_USER: {db_user}")
    print(f"DB_PASSWORD: {'***' if db_password else '❌ NOT SET'}")
    print(f"DB_HOST: {db_host or '❌ NOT SET'}")
    print(f"DB_PORT: {db_port}")
    print(f"DB_NAME: {db_name}")

    # Validate required components
    missing_vars = []
    if not db_password:
        missing_vars.append("DB_PASSWORD")
    if not db_host:
        missing_vars.append("DB_HOST")

    if missing_vars:
        error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
        print(f"❌ {error_msg}")
        print("\n💡 SOLUTION:")
        print("1. Create a .env file in your project root")
        print("2. Add your database credentials:")
        print("   DATABASE_URL=postgresql://user:password@host:port/database")
        print("   OR individual variables:")
        print("   DB_PASSWORD=your-password")
        print("   DB_HOST=your-host")
        print("3. Get your Supabase connection string from:")
        print("   Project Settings > Database > Connection string")
        raise ValueError(error_msg)

    # Build URL without sslmode (asyncpg handles SSL automatically)
    database_url = f"postgresql+asyncpg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    print("✅ Database URL built successfully (SSL will be handled by asyncpg)")
    return database_url


# Global database variables
engine = None
async_session_maker = None


async def initialize_db():
    """Initialize database connection - Fixed for asyncpg prepared statement issue"""
    global engine, async_session_maker

    try:
        print("=== INITIALIZING DATABASE ===")
        database_url = get_database_url()

        # CRITICAL FIX: Configure asyncpg to disable prepared statements
        # This resolves the DuplicatePreparedStatementError
        connect_args = {
            "server_settings": {
                "application_name": "leaderboard_service",
            },
            # SOLUTION 1: Disable prepared statement cache completely
            "prepared_statement_cache_size": 0,
            # SOLUTION 2: Alternative - use a unique cache name per connection
            # "prepared_statement_name_func": lambda: f"stmt_{id(object())}"
        }

        # For Supabase and other cloud providers, asyncpg handles SSL automatically
        # We don't need to specify SSL parameters explicitly
        engine = create_async_engine(
            database_url,
            echo=os.getenv("SQL_ECHO", "false").lower() == "true",
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=3600,
            connect_args=connect_args
        )

        async_session_maker = sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

        # Test the connection
        async with async_session_maker() as session:
            await session.execute(select(1))

        print("✅ Database initialization successful")
        print("✅ Prepared statement cache disabled - issue resolved")

    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        print("\n💡 TROUBLESHOOTING:")
        print("1. Verify your database credentials are correct")
        print("2. Check your internet connection")
        print("3. Ensure your database server is running")
        print("4. Verify the database URL format")
        print("5. For Supabase: ensure you're using the connection pooler URL")
        print("6. Remove any sslmode parameters from your DATABASE_URL")
        print("7. If using PgBouncer, ensure pool_mode is set to 'session'")
        raise


async def get_db():
    """Database dependency for FastAPI"""
    if not async_session_maker:
        await initialize_db()

    async with async_session_maker() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            raise
        finally:
            await session.close()


async def sync_redis_with_postgresql():
    """Background task to sync PostgreSQL data to Redis"""
    print("🔄 Starting Redis-PostgreSQL sync task...")

    while True:
        try:
            if not async_session_maker:
                await initialize_db()

            async with async_session_maker() as db:
                result = await db.execute(select(Leaderboard))
                entries = result.scalars().all()

                # Group entries by course for efficient Redis operations
                courses = {}
                for entry in entries:
                    if entry.course_id not in courses:
                        courses[entry.course_id] = {}
                    courses[entry.course_id][entry.username] = entry.score

                # Update Redis with pipeline for efficiency
                with redis_client.pipeline() as pipe:
                    for course_id, players in courses.items():
                        redis_key = f"{LEADERBOARD_PREFIX}{course_id}"
                        pipe.zadd(redis_key, players)
                    pipe.execute()

                print(f"✅ Synced {len(entries)} entries across {len(courses)} courses to Redis")

        except Exception as e:
            print(f"❌ Sync error: {e}")
            await asyncio.sleep(60)  # Wait before retrying
            continue

        await asyncio.sleep(300)  # Sync every 5 minutes


async def test_connections():
    """Test both database and Redis connections"""
    print("=== TESTING CONNECTIONS ===")

    try:
        # Test database
        if not async_session_maker:
            await initialize_db()

        async with async_session_maker() as db:
            result = await db.execute(select(1))
            print("✅ Database connection test passed")

        # Test Redis
        result = redis_client.ping()
        print(f"✅ Redis connection test passed: {result}")

        # Test Redis operations
        test_key = "test_connection"
        redis_client.set(test_key, "test_value", ex=60)
        value = redis_client.get(test_key)
        redis_client.delete(test_key)
        print(f"✅ Redis operations test passed: {value}")

        print("✅ All connection tests passed")
        return True

    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        raise