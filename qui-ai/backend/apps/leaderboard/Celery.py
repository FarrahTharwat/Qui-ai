import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()
celery_app = Celery(
    "leaderboard",
    broker=os.getenv("CELERY_BROKER_URL"),
    backend=os.getenv("CELERY_BROKER_URL"),
)

celery_app.conf.update(
    broker_connection_retry_on_startup=True,
    broker_use_ssl={'ssl_cert_reqs': 'CERT_NONE'},
    redis_backend_use_ssl={'ssl_cert_reqs': 'CERT_NONE'},
    task_routes={
        "worker.update_leaderboard": {"queue": "leaderboard"},
    }
)

@celery_app.task
def test_task():
    print("Celery is working!")