# redis_debug.py
"""
Debug script to test Redis connection and operations
"""

import os
import json
import redis
from urllib.parse import urlparse
import logging
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_redis_connection():
    """Test Redis connection with different methods"""

    print("=== Redis Connection Debug ===")
    print(f"Current time: {datetime.now()}")

    # Check environment variables
    redis_url = os.getenv("REDIS_URL")
    redis_host = os.getenv("REDIS_HOST", "localhost")
    redis_port = int(os.getenv("REDIS_PORT", "6379"))
    redis_password = os.getenv("REDIS_PASSWORD")
    redis_username = os.getenv("REDIS_USERNAME", "default")

    print("\n=== Environment Variables ===")
    print(f"REDIS_URL: {redis_url[:50] + '...' if redis_url and len(redis_url) > 50 else redis_url}")
    print(f"REDIS_HOST: {redis_host}")
    print(f"REDIS_PORT: {redis_port}")
    print(f"REDIS_PASSWORD: {'***' if redis_password else 'None'}")
    print(f"REDIS_USERNAME: {redis_username}")

    # Test 1: Direct URL connection (Redis Cloud method)
    if redis_url:
        print("\n=== Test 1: URL Connection ===")
        try:
            # Parse URL for debugging
            parsed = urlparse(redis_url)
            print(f"Parsed URL - Host: {parsed.hostname}, Port: {parsed.port}, SSL: {parsed.scheme == 'rediss'}")

            client = redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=10,
                socket_timeout=10,
                retry_on_timeout=True,
                health_check_interval=30,
                ssl_cert_reqs=None,  # Critical for Redis Cloud
                retry_on_error=[redis.ConnectionError, redis.TimeoutError]
            )

            # Test connection
            result = client.ping()
            print(f"✅ URL Connection successful: {result}")

            # Test basic operations
            test_key = "debug_test"
            test_value = {"timestamp": datetime.now().isoformat(), "test": "data"}

            # Set data
            client.setex(test_key, 60, json.dumps(test_value))
            print(f"✅ Set test data with key: {test_key}")

            # Get data
            retrieved = client.get(test_key)
            if retrieved:
                parsed_data = json.loads(retrieved)
                print(f"✅ Retrieved test data: {parsed_data}")
            else:
                print("❌ Failed to retrieve test data")

            # List keys
            keys = client.keys("*")
            print(f"✅ Total keys in database: {len(keys)}")
            if keys:
                print(f"Sample keys: {keys[:5]}")

            # Clean up
            client.delete(test_key)
            print(f"✅ Cleaned up test key")

            return client

        except Exception as e:
            print(f"❌ URL Connection failed: {e}")

    # Test 2: Manual connection parameters
    print("\n=== Test 2: Manual Connection ===")
    try:
        connection_params = {
            'host': redis_host,
            'port': redis_port,
            'db': 0,
            'decode_responses': True,
            'socket_connect_timeout': 10,
            'socket_timeout': 10,
            'retry_on_timeout': True
        }

        if redis_password:
            connection_params['password'] = redis_password

        if redis_username and redis_username != 'default':
            connection_params['username'] = redis_username

        # SSL for Redis Cloud
        if redis_url and 'rediss://' in redis_url:
            connection_params['ssl'] = True
            connection_params['ssl_cert_reqs'] = None

        print(f"Connection params: {dict((k, '***' if 'password' in k else v) for k, v in connection_params.items())}")

        client = redis.Redis(**connection_params)
        result = client.ping()
        print(f"✅ Manual Connection successful: {result}")

        return client

    except Exception as e:
        print(f"❌ Manual Connection failed: {e}")

    return None


def test_your_redis_manager():
    """Test your actual Redis manager"""
    print("\n=== Testing Your Redis Manager ===")

    try:
        # Import your modules
        from app.config.database import get_redis_manager

        redis_manager = get_redis_manager()

        print(f"Redis manager created: {redis_manager}")
        print(f"Is available: {redis_manager.is_available()}")

        if redis_manager.is_available():
            # Test ping
            ping_result = redis_manager.ping()
            print(f"Ping result: {ping_result}")

            # Test setting processing data
            test_session_id = "debug_session_12345"
            test_data = {
                "success": True,
                "pdf_path": "/test/path.pdf",
                "polished_pages": {"1": "test page content"},
                "timestamp": datetime.now().isoformat()
            }

            print(f"Testing set_processing_data for session: {test_session_id}")
            set_result = redis_manager.set_processing_data(test_session_id, test_data, ttl=300)
            print(f"Set result: {set_result}")

            # Test getting processing data
            print(f"Testing get_processing_data for session: {test_session_id}")
            get_result = redis_manager.get_processing_data(test_session_id)
            print(f"Get result: {get_result}")

            # Test setting status
            print(f"Testing set_session_status for session: {test_session_id}")
            status_result = redis_manager.set_session_status(
                test_session_id,
                "processed",
                {"test": "metadata"}
            )
            print(f"Status set result: {status_result}")

            # Test getting status
            print(f"Testing get_session_status for session: {test_session_id}")
            status_get_result = redis_manager.get_session_status(test_session_id)
            print(f"Status get result: {status_get_result}")

            # List all keys
            if redis_manager.client:
                all_keys = redis_manager.client.keys("*")
                print(f"All keys in Redis: {all_keys}")

                # Show processing keys specifically
                processing_keys = [k for k in all_keys if k.startswith("processing:")]
                status_keys = [k for k in all_keys if k.startswith("status:")]

                print(f"Processing keys: {processing_keys}")
                print(f"Status keys: {status_keys}")

            # Cleanup
            redis_manager.delete_processing_data(test_session_id)
            redis_manager.delete_cache(f"status:{test_session_id}")
            print("✅ Cleanup completed")

        else:
            print("❌ Redis manager not available")

    except Exception as e:
        print(f"❌ Error testing Redis manager: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main debug function"""
    print("Starting Redis Debug Session...")

    # Test direct connection
    client = test_redis_connection()

    # Test your manager
    test_your_redis_manager()

    print("\n=== Debug Session Complete ===")


if __name__ == "__main__":
    main()