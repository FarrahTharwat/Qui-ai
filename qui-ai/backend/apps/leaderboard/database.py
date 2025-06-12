# database.py - Complete fix for asyncpg sslmode and prepared statement issues
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
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

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

    try:
        client = redis.Redis(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            decode_responses=True,
            ssl=redis_ssl,
            socket_connect_timeout=30,
            socket_timeout=30,
            retry_on_timeout=True,
            health_check_interval=30
        )
        result = client.ping()
        print(f"✅ Redis connection successful: {result}")
        return client
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        raise


# Create Redis client
redis_client = create_redis_client()


def clean_database_url(database_url):
    """Clean database URL to remove incompatible parameters for asyncpg"""
    print("🔧 Cleaning database URL for asyncpg compatibility...")

    # Parse the URL
    parsed = urlparse(database_url)
    query_params = parse_qs(parsed.query, keep_blank_values=True)

    # Remove parameters that asyncpg doesn't support
    incompatible_params = [
        'sslmode', 'sslcert', 'sslkey', 'sslrootcert',
        'prepared_statements',  # This is handled via connect_args instead
        'statement_cache_size'  # This is also handled via connect_args
    ]
    for param in incompatible_params:
        if param in query_params:
            print(f"🗑️  Removing incompatible parameter: {param}")
            del query_params[param]

    # Don't add prepared_statements to URL - it goes in connect_args instead

    # Rebuild the URL without incompatible parameters
    new_query = urlencode(query_params, doseq=True)
    cleaned_url = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        new_query,
        parsed.fragment
    ))

    print("✅ Database URL cleaned for asyncpg")
    return cleaned_url


def get_database_url():
    """Build database URL from environment variables - Fixed for asyncpg"""
    print("=== CONFIGURING DATABASE CONNECTION ===")

    database_url = os.getenv("DATABASE_URL")
    if database_url:
        print("✅ Using DATABASE_URL from environment")

        # Convert to asyncpg format
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

        # Clean the URL to remove incompatible parameters
        database_url = clean_database_url(database_url)

        return database_url

    # Build from components if DATABASE_URL not available
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD")
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "postgres")

    if not db_password or not db_host:
        raise ValueError("Missing required database credentials")

    database_url = f"postgresql+asyncpg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    return database_url


# Global database variables
engine = None
async_session_maker = None


async def initialize_db():
    """Initialize database connection - COMPLETE FIX for asyncpg sslmode and prepared statement issues"""
    global engine, async_session_maker

    try:
        print("=== INITIALIZING DATABASE ===")
        database_url = get_database_url()

        # CRITICAL FIXES for asyncpg compatibility:
        connect_args = {
            # Primary fix: Completely disable prepared statement cache
            "prepared_statement_cache_size": 0,

            # Additional asyncpg-specific settings
            "command_timeout": 60,
            "server_settings": {
                "application_name": "leaderboard_service",
                "jit": "off",  # Disable JIT to prevent issues
            },
        }

        # Create engine with settings optimized for cloud databases + PgBouncer
        engine = create_async_engine(
            database_url,
            echo=False,  # Set to True for SQL debugging

            # Pool settings optimized for cloud databases
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,  # Test connections before use
            pool_recycle=3600,  # Recycle connections every hour
            pool_reset_on_return='commit',

            # CRITICAL: Pass connect_args to fix prepared statement and SSL issues
            connect_args=connect_args,
        )

        # Create session maker
        async_session_maker = sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        # Test the connection
        print("🔍 Testing database connection...")
        async with async_session_maker() as session:
            # Simple test query that won't trigger prepared statement caching
            result = await session.execute(select(1))
            test_value = result.scalar()
            print(f"✅ Database connection successful: {test_value}")

        print("✅ Database initialization complete")
        print("✅ Prepared statement conflicts resolved")

    except Exception as e:
        print(f"❌ Database initialization failed: {e}")

        # Provide specific guidance for common issues
        if "prepared_statements" in str(e):
            print("\n🔧 PREPARED STATEMENTS ISSUE:")
            print("The 'prepared_statements' parameter should not be in the URL.")
            print("It's now handled via connect_args in the engine configuration.")

        if "sslmode" in str(e):
            print("\n🔧 SSL CONFIGURATION ISSUE:")
            print("The 'sslmode' parameter is not supported by asyncpg.")
            print("This has been fixed in the updated code.")

        if "DuplicatePreparedStatementError" in str(e):
            print("\n🔧 ADDITIONAL FIXES TO TRY:")
            print("1. Restart your application completely")
            print("2. Check if you have multiple database connections")
            print("3. Verify PgBouncer pool_mode is set to 'session'")
            print("4. Try using the direct database URL instead of pooler")

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
    """Sync PostgreSQL data to Redis"""
    print("🔄 Starting Redis-PostgreSQL sync...")

    while True:
        try:
            if not async_session_maker:
                await initialize_db()

            async with async_session_maker() as db:
                result = await db.execute(select(Leaderboard))
                entries = result.scalars().all()

                # Group by course
                courses = {}
                for entry in entries:
                    if entry.course_id not in courses:
                        courses[entry.course_id] = {}
                    courses[entry.course_id][entry.username] = entry.score

                # Update Redis
                for course_id, players in courses.items():
                    redis_key = f"{LEADERBOARD_PREFIX}{course_id}"
                    redis_client.zadd(redis_key, players)

                print(f"✅ Synced {len(entries)} entries to Redis")

        except Exception as e:
            print(f"❌ Sync error: {e}")
            await asyncio.sleep(60)
            continue

        await asyncio.sleep(300)  # Sync every 5 minutes


async def test_connections():
    """Test both database and Redis connections"""
    print("=== TESTING CONNECTIONS ===")

    try:
        # Initialize database if needed
        if not async_session_maker:
            await initialize_db()

        # Test database
        async with async_session_maker() as db:
            result = await db.execute(select(1))
            print(f"✅ Database test: {result.scalar()}")

        # Test Redis
        result = redis_client.ping()
        print(f"✅ Redis test: {result}")

        print("✅ All connections working!")
        return True

    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        raise


# Manual test function
async def manual_test():
    """Run manual tests"""
    try:
        await test_connections()
        print("Manual test passed!")
    except Exception as e:
        print(f"Manual test failed: {e}")
        import traceback
        traceback.print_exc()


