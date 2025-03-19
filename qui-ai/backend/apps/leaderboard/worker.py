from celery import shared_task
from .database import redis_client, async_session_maker
from sqlalchemy.future import select
import asyncio
from .models import Leaderboard
from celery import Celery
import os

celery = Celery(
    "leaderboard",
    broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0")
)
@celery.task
def test_task():
    return "Celery is working!"

@shared_task
def update_leaderboard(scores):
    """
    Background task to update leaderboard scores.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(process_updates(scores))

async def process_updates(scores):
    """
    Asynchronous function to process leaderboard updates.
    """
    async with async_session_maker() as db:
        for entry in scores:
            leaderboard_key = f"leaderboard:{entry['course_id']}"
            redis_client.zadd(leaderboard_key, {entry['username']: entry['score']})

            # Update PostgreSQL as well
            result = await db.execute(
                select(Leaderboard).where(Leaderboard.course_id == entry['course_id'], Leaderboard.username == entry['username'])
            )
            existing_entry = result.scalar_one_or_none()

            if existing_entry:
                existing_entry.score = max(existing_entry.score, entry['score'])  # Update only if the score is higher
            else:
                db.add(Leaderboard(course_id=entry['course_id'], username=entry['username'], score=entry['score']))

        await db.commit()
