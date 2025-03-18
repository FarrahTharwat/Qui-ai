from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Follower, Achievement
from .tasks import send_in_app_notification

@receiver(post_save, sender=Follower)
def new_follower_notification(sender, instance, created, **kwargs):
    if created:
        message = f"{instance.follower.username} started following you! 🎉"
        send_in_app_notification(instance.following, message)

@receiver(post_save, sender=Achievement)
def new_achievement_notification(sender, instance, created, **kwargs):
    if created:
        message = f"🎖️ Congrats {instance.user.username}, you unlocked '{instance.title}'!"
        send_in_app_notification(instance.user, message)
