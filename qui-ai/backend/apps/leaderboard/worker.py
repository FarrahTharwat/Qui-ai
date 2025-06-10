# Fixed worker.py (Optional - for Celery background tasks)
from celery_app import celery_app
from database import redis_client, get_database_url
from models import Leaderboard
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
from sqlalchemy import and_
import asyncio
import logging

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def update_leaderboard(self, scores):
    """Celery task to update leaderboard data"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(process_updates(scores))
        loop.close()
        return result
    except Exception as e:
        logger.error(f"Leaderboard update failed: {e}")
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


async def process_updates(scores):
    """Process leaderboard updates asynchronously"""
    database_url = get_database_url()
    engine = create_async_engine(database_url)
    session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    updated_count = 0

    try:
        async with session_maker() as db:
            for entry in scores:
                try:
                    course_id = entry['course_id']
                    username = entry['username']
                    score = entry['score']

                    # Update Redis immediately
                    leaderboard_key = f"course_leaderboard:{course_id}"
                    redis_client.zadd(leaderboard_key, {username: score})

                    # Check if entry exists in database
                    result = await db.execute(
                        select(Leaderboard).where(
                            and_(
                                Leaderboard.course_id == course_id,
                                Leaderboard.username == username
                            )
                        )
                    )
                    existing = result.scalar_one_or_none()

                    if existing:
                        if score > existing.score:
                            existing.score = score
                            logger.info(f"Updated score for {username} in {course_id}: {score}")
                    else:
                        new_entry = Leaderboard(
                            course_id=course_id,
                            username=username,
                            score=score
                        )
                        db.add(new_entry)
                        logger.info(f"Added new entry for {username} in {course_id}: {score}")

                    updated_count += 1

                except Exception as entry_error:
                    logger.error(f"Failed to process entry {entry}: {entry_error}")
                    continue

            await db.commit()
            logger.info(f"Successfully processed {updated_count} leaderboard updates")

    except Exception as db_error:
        logger.error(f"Database operation failed: {db_error}")
        raise
    finally:
        await engine.dispose()

    return {
        "processed": len(scores),
        "updated": updated_count,
        "status": "success"
    }