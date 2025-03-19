from celery import Celery
import os

# Redis broker URL
CELERY_BROKER_URL = "redis://redis:6379/0"  # No password
CELERY_RESULT_BACKEND = "redis://redis:6379/0"  # No password

# Initialize Celery app
celery_app = Celery(
    "leaderboard_tasks",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["apps.leaderboard.worker"]  # Ensure Celery can find the worker tasks
)

# Update Celery configuration
celery_app.conf.update(
    broker_connection_retry_on_startup = True,
    task_routes={
        "worker.update_leaderboard": {"queue": "leaderboard"},
    }
)

celery = Celery("leaderboard", broker="redis://redis:6379/0")

@celery.task
def test_task():
    print("Celery is working!")

if __name__ == "__main__":
    celery_app.start()
