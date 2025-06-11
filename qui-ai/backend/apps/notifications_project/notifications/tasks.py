from celery import shared_task
from django.utils.timezone import now
from django.contrib.auth.models import User
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import Notification
from celery import shared_task
import random


# List of motivational messages
MOTIVATIONAL_MESSAGES = [
    "Keep going, you're doing great! 💪",
    "Small progress is still progress! 🚀",
    "Your AI journey is just beginning! 🤖",
    "Never stop learning, your future self will thank you! 📚",
    "One step closer to mastering AI! 🔥"
]

def send_in_app_notification(user, message):
    """Store and send a notification to the user"""
    # Save to DB
    Notification.objects.create(user=user, message=message)

    # Send in real-time
    channel_layer = get_channel_layer()
    
    if channel_layer is None:
        print(f"Error: Channel layer is not available for user {user.id}")
        return
    
    try:
        async_to_sync(channel_layer.group_send)(
            f"user_{user.id}",
            {"type": "send_notification", "message": message}
        )
    except Exception as e:
        print(f"Failed to send notification to user {user.id}: {e}")


@shared_task
def send_motivational_message():
    try:
        users = User.objects.all()

        for user in users:
            # Check if user has completed the lesson
            user_has_completed_lesson = False  # Placeholder logic

            if not user_has_completed_lesson:
                message = random.choice(MOTIVATIONAL_MESSAGES)
                send_in_app_notification(user, message)
                print(f"Motivational message sent to User {user.id}: {message}")
    except Exception as e:
        print(f"Error in sending motivational message: {e}")



@shared_task
def check_streak_loss():
    """Check if a user lost their streak and notify them after midnight"""
    print("Running check_streak_loss task...")

    users = User.objects.all()
    
    for user in users:
        streak_lost = True  # Placeholder for real streak tracking
        
        if streak_lost:
            message = "Oops! You lost your streak. Get back on track now! 🔥"
            send_in_app_notification(user, message)
            print(f"Streak loss notification sent to User {user.id}")

    print("Finished check_streak_loss task.")
