# test_connections.py - Run this script to test your connections
import os
import redis
from pathlib import Path
from dotenv import load_dotenv, find_dotenv


def load_env_with_debug():
    """Load environment with detailed debugging"""
    print("=== ENVIRONMENT LOADING DEBUG ===")

    # Check current directory
    current_dir = Path.cwd()
    print(f"Current directory: {current_dir}")

    # List all files in current directory
    files = list(current_dir.glob("*"))
    print(f"Files in current directory: {[f.name for f in files]}")

    # Check for .env files
    env_files = list(current_dir.glob(".env*"))
    print(f"Found .env files: {[f.name for f in env_files]}")

    # Try different loading methods
    env_loaded = False

    # Method 1: Direct path
    env_path = current_dir / ".env"
    if env_path.exists():
        print(f"Loading .env from: {env_path}")
        result = load_dotenv(env_path, verbose=True, override=True)
        print(f"Load result: {result}")
        env_loaded = True

    # Method 2: find_dotenv
    if not env_loaded:
        found_env = find_dotenv()
        if found_env:
            print(f"Found .env using find_dotenv: {found_env}")
            result = load_dotenv(found_env, verbose=True, override=True)
            print(f"Load result: {result}")
            env_loaded = True

    if not env_loaded:
        print("❌ No .env file loaded!")
        print("Please create a .env file in your project root")
        return False

    return True


def test_redis_connection():
    """Test Redis connection with detailed output"""
    print("\n=== REDIS CONNECTION TEST ===")

    # Print environment variables
    redis_vars = {
        'REDIS_URL': os.getenv('REDIS_URL'),
        'REDIS_HOST': os.getenv('REDIS_HOST'),
        'REDIS_PORT': os.getenv('REDIS_PORT'),
        'REDIS_PASSWORD': os.getenv('REDIS_PASSWORD'),
        'REDIS_USERNAME': os.getenv('REDIS_USERNAME'),
        'REDIS_SSL': os.getenv('REDIS_SSL')
    }

    for key, value in redis_vars.items():
        if value:
            if 'PASSWORD' in key or 'URL' in key:
                masked = value[:10] + "..." + value[-4:] if len(value) > 14 else "***"
                print(f"{key}: {masked}")
            else:
                print(f"{key}: {value}")
        else:
            print(f"{key}: NOT SET")

    # Test Method 1: Using REDIS_URL
    redis_url = os.getenv('REDIS_URL')
    if redis_url:
        print(f"\nTesting with REDIS_URL...")
        try:
            client = redis.from_url(
                redis_url,
                decode_responses=True,
                ssl_cert_reqs=None,
                socket_connect_timeout=10,
                socket_timeout=10
            )
            result = client.ping()
            print(f"✅ REDIS_URL connection successful: {result}")

            # Test basic operations
            client.set('test_key', 'test_value', ex=30)
            value = client.get('test_key')
            client.delete('test_key')
            print(f"✅ Redis operations test passed: {value}")
            return True

        except Exception as e:
            print(f"❌ REDIS_URL connection failed: {e}")

    # Test Method 2: Using individual parameters
    redis_host = os.getenv('REDIS_HOST')
    redis_port = int(os.getenv('REDIS_PORT', 6379))
    redis_password = os.getenv('REDIS_PASSWORD')
    redis_ssl = os.getenv('REDIS_SSL', 'false').lower() == 'true'

    if redis_host and redis_password:
        print(f"\nTesting with individual parameters...")
        try:
            config = {
                'host': redis_host,
                'port': redis_port,
                'password': redis_password,
                'decode_responses': True,
                'socket_connect_timeout': 10,
                'socket_timeout': 10
            }

            if redis_ssl:
                config['ssl'] = True
                config['ssl_cert_reqs'] = None

            client = redis.Redis(**config)
            result = client.ping()
            print(f"✅ Parameter connection successful: {result}")
            return True

        except Exception as e:
            print(f"❌ Parameter connection failed: {e}")

    print("❌ All Redis connection methods failed!")
    return False


def main():
    """Main test function"""
    print("=== CONNECTION TESTING SCRIPT ===\n")

    # Load environment
    if not load_env_with_debug():
        print("\n❌ Failed to load environment variables")
        return

    # Test Redis
    if test_redis_connection():
        print("\n✅ All tests passed! Your Redis connection is working.")
    else:
        print("\n❌ Redis connection failed. Please check your configuration.")
        print("\nTROUBLESHOoting:")
        print("1. Verify your .env file exists in the project root")
        print("2. Check Redis Cloud credentials are correct")
        print("3. Ensure your internet connection is working")
        print("4. Try the Redis Cloud console to verify your instance is running")


if __name__ == "__main__":
    main()