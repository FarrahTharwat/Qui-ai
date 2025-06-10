import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

# Get Redis connection details
redis_host = os.getenv("REDIS_HOST", "localhost")
redis_port = os.getenv("REDIS_PORT", "6379")
redis_password = os.getenv("REDIS_PASSWORD")
redis_ssl = os.getenv("REDIS_SSL", "false").lower() == "true"

# Build Redis URL for Celery
if redis_password:
    if redis_ssl:
        broker_url = f"rediss://default:{redis_password}@{redis_host}:{redis_port}/0"
    else:
        broker_url = f"redis://default:{redis_password}@{redis_host}:{redis_port}/0"
else:
    broker_url = f"redis://{redis_host}:{redis_port}/0"

# Use environment variable if provided, otherwise use constructed URL
celery_broker_url = os.getenv("CELERY_BROKER_URL", broker_url)

celery_app = Celery(
    "leaderboard",
    broker=celery_broker_url,
    backend=celery_broker_url,
)

# Celery configuration
celery_app.conf.update(
    broker_connection_retry_on_startup=True,
    task_routes={
        "worker.update_leaderboard": {"queue": "leaderboard"},
    },
    # SSL configuration for Redis Cloud
    broker_use_ssl={
        'ssl_cert_reqs': 'CERT_NONE'
    } if redis_ssl else None,
    redis_backend_use_ssl={
        'ssl_cert_reqs': 'CERT_NONE'
    } if redis_ssl else None,
    # Task settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    # Result backend settings
    result_expires=3600,  # 1 hour
)

@celery_app.task
def test_task():
    """Test task to verify Celery is working"""
    print("Celery is working with Supabase!")
    return "Success"