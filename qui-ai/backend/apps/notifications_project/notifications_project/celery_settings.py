from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    "send_motivational_message_daily": {
        "task": "notifications.tasks.send_motivational_message",
        "schedule": crontab(hour=23, minute=50),  # 11:50 PM
    },
    "check_streak_loss": {
        "task": "notifications.tasks.check_streak_loss",
        "schedule": crontab(hour=0, minute=5),  # 12:05 AM
    },
}

