# fixed_redis_test.py - Fixed Redis Cloud connection test
import os
import redis
import ssl
from pathlib import Path
from dotenv import load_dotenv


def load_env():
    """Load environment variables"""
    env_path = Path.cwd() / ".env"
    if env_path.exists():
        load_dotenv(env_path, verbose=True, override=True)
        print("✅ .env file loaded successfully")
        return True
    else:
        print("❌ .env file not found")
        return False


def test_redis_methods():
    """Test multiple Redis connection methods for Redis Cloud"""
    print("=== TESTING REDIS CLOUD CONNECTION ===")

    redis_url = os.getenv('REDIS_URL')
    redis_host = os.getenv('REDIS_HOST')
    redis_port = int(os.getenv('REDIS_PORT', 6379))
    redis_password = os.getenv('REDIS_PASSWORD')

    print(f"REDIS_HOST: {redis_host}")
    print(f"REDIS_PORT: {redis_port}")
    print(f"REDIS_PASSWORD: {'***' if redis_password else 'Not set'}")

    # Method 1: Redis URL with proper SSL context
    if redis_url:
        print(f"\n🔧 Method 1: Redis URL with custom SSL context")
        try:
            # Create custom SSL context for Redis Cloud
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            client = redis.from_url(
                redis_url,
                decode_responses=True,
                ssl_cert_reqs=None,
                ssl_check_hostname=False,
                ssl_context=ssl_context,
                socket_connect_timeout=10,
                socket_timeout=10,
                retry_on_timeout=True
            )

            result = client.ping()
            print(f"✅ Method 1 SUCCESS: {result}")

            # Test operations
            client.set('test_key', 'test_value', ex=30)
            value = client.get('test_key')
            client.delete('test_key')
            print(f"✅ Redis operations successful: {value}")
            return client

        except Exception as e:
            print(f"❌ Method 1 failed: {e}")

    # Method 2: Individual parameters with SSL
    if redis_host and redis_password:
        print(f"\n🔧 Method 2: Individual parameters with SSL")
        try:
            client = redis.Redis(
                host=redis_host,
                port=redis_port,
                password=redis_password,
                decode_responses=True,
                ssl=True,
                ssl_cert_reqs=None,
                ssl_check_hostname=False,
                socket_connect_timeout=10,
                socket_timeout=10,
                retry_on_timeout=True
            )

            result = client.ping()
            print(f"✅ Method 2 SUCCESS: {result}")
            return client

        except Exception as e:
            print(f"❌ Method 2 failed: {e}")

    # Method 3: Try without SSL (in case Redis Cloud supports both)
    if redis_host and redis_password:
        print(f"\n🔧 Method 3: Without SSL (fallback)")
        try:
            client = redis.Redis(
                host=redis_host,
                port=redis_port,
                password=redis_password,
                decode_responses=True,
                ssl=False,
                socket_connect_timeout=10,
                socket_timeout=10,
                retry_on_timeout=True
            )

            result = client.ping()
            print(f"✅ Method 3 SUCCESS: {result}")
            return client

        except Exception as e:
            print(f"❌ Method 3 failed: {e}")

    # Method 4: Redis URL with modified SSL settings
    if redis_url:
        print(f"\n🔧 Method 4: Modified Redis URL")
        try:
            # Modify URL to use redis:// instead of rediss://
            modified_url = redis_url.replace('rediss://', 'redis://')

            client = redis.from_url(
                modified_url,
                decode_responses=True,
                socket_connect_timeout=10,
                socket_timeout=10,
                retry_on_timeout=True
            )

            result = client.ping()
            print(f"✅ Method 4 SUCCESS: {result}")
            return client

        except Exception as e:
            print(f"❌ Method 4 failed: {e}")

    print("❌ All Redis connection methods failed!")
    return None


def test_database_connection():
    """Test database connection"""
    print("\n=== TESTING DATABASE CONNECTION ===")

    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL not found")
        return False

    print(f"DATABASE_URL: {database_url[:50]}...")

    try:
        import asyncpg
        import asyncio

        async def test_db():
            # Convert to asyncpg format
            if database_url.startswith("postgresql://"):
                asyncpg_url = database_url
            else:
                asyncpg_url = database_url.replace("postgresql+asyncpg://", "postgresql://")

            conn = await asyncpg.connect(asyncpg_url)
            result = await conn.fetchval('SELECT 1')
            await conn.close()
            return result

        result = asyncio.run(test_db())
        print(f"✅ Database connection successful: {result}")
        return True

    except ImportError:
        print("⚠️  asyncpg not installed, skipping database test")
        print("Install with: pip install asyncpg")
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False


def main():
    """Main test function"""
    print("=== IMPROVED CONNECTION TEST ===\n")

    # Load environment
    if not load_env():
        return

    # Test Redis
    redis_client = test_redis_methods()
    if redis_client:
        print("\n✅ Redis connection established successfully!")

        # Test Redis operations
        try:
            print("\n🔧 Testing Redis operations...")
            redis_client.set('test_leaderboard', '{"player1": 100, "player2": 90}', ex=60)
            value = redis_client.get('test_leaderboard')
            redis_client.delete('test_leaderboard')
            print(f"✅ Leaderboard test successful: {value}")
        except Exception as e:
            print(f"❌ Redis operations failed: {e}")
    else:
        print("\n❌ Could not establish Redis connection")
        print("\nTroubleshooting suggestions:")
        print("1. Check if your Redis Cloud instance is active")
        print("2. Verify the credentials are correct")
        print("3. Try accessing Redis Cloud console to confirm connectivity")
        print("4. Check if your IP is whitelisted (if IP restrictions are enabled)")

    # Test Database
    test_database_connection()

    print("\n=== TEST COMPLETE ===")


if __name__ == "__main__":
    main()