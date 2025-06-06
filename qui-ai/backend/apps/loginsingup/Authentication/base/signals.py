from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver
from .models import UserProfile

@receiver(post_save, sender=User)
def create_or_update_profile(sender, instance, created, **kwargs):
    if created:
        # Create profile when a new user is created
        UserProfile.objects.create(user=instance)
    else:
        # Save profile when user is updated
        instance.userprofile.save()

