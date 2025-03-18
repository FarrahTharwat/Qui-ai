from celery import shared_task
from django.utils.timezone import now
from django.contrib.auth.models import User
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
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
    """Send a notification to the user via Django Channels"""
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
    """Send a random motivational message before 12 AM if the user hasn't completed a lesson"""
    print("Running send_motivational_message task...")

    users = User.objects.all()
    
    for user in users:
        user_has_completed_lesson = False  # Placeholder for real progress check
        
        if not user_has_completed_lesson:
            message = random.choice(MOTIVATIONAL_MESSAGES)
            send_in_app_notification(user, message)
            print(f"Motivational message sent to User {user.id}: {message}")

    print("Finished send_motivational_message task.")


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
