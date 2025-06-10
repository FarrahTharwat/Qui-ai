"""
Redis Cloud Connection Configuration
"""

import redis
import os
from urllib.parse import urlparse


# Method 1: Direct connection with parameters
def create_redis_connection():
    """Create Redis connection using individual parameters"""
    return redis.Redis(
        host='redis-16617.c245.us-east-1-3.ec2.redns.redis-cloud.com',
        port=16617,
        username='default',
        password='q7vaO90Ie5M2poP1OE8czfEgvUMKaRlr',
        ssl=True,
        ssl_cert_reqs=None,
        decode_responses=True
    )


# Method 2: Using environment variables
def create_redis_from_env():
    """Create Redis connection using environment variables"""
    return redis.Redis(
        host=os.getenv('REDIS_HOST'),
        port=int(os.getenv('REDIS_PORT', 6379)),
        username=os.getenv('REDIS_USERNAME'),
        password=os.getenv('REDIS_PASSWORD'),
        ssl=os.getenv('REDIS_SSL', 'false').lower() == 'true',
        ssl_cert_reqs=None,
        decode_responses=True
    )


# Method 3: Using Redis URL
def create_redis_from_url():
    """Create Redis connection using URL"""
    redis_url = os.getenv('REDIS_URL',
                          'rediss://default:q7vaO90Ie5M2poP1OE8czfEgvUMKaRlr@redis-16617.c245.us-east-1-3.ec2.redns.redis-cloud.com:16617')
    return redis.from_url(redis_url, decode_responses=True, ssl_cert_reqs=None)


# Example usage
if __name__ == "__main__":
    # Test connection
    try:
        r = create_redis_connection()

        # Test basic operations
        success = r.set('test_key', 'Hello Redis!')
        print(f"Set operation successful: {success}")

        result = r.get('test_key')
        print(f"Retrieved value: {result}")

        # Test ping
        ping_result = r.ping()
        print(f"Ping successful: {ping_result}")

    except Exception as e:
        print(f"Redis connection failed: {e}")

# For use with Celery
CELERY_CONFIG = {
    'broker_url': 'rediss://default:q7vaO90Ie5M2poP1OE8czfEgvUMKaRlr@redis-16617.c245.us-east-1-3.ec2.redns.redis-cloud.com:16617',
    'result_backend': 'rediss://default:q7vaO90Ie5M2poP1OE8czfEgvUMKaRlr@redis-16617.c245.us-east-1-3.ec2.redns.redis-cloud.com:16617',
    'broker_connection_retry_on_startup': True,
    'result_expires': 3600,
}