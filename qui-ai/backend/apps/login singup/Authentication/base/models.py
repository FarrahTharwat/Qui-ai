from django.contrib.auth.models import User
from django.db import models

# class UserProfile(models.Model):
#     user = models.OneToOneField(User, on_delete=models.CASCADE)
#     bio = models.TextField()

#     def __str__(self):
#         return f"{self.user.username} - {self.bio}"



class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=100)
    bio = models.TextField(blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', default='default.jpg')
    phone = models.CharField(max_length=15, blank=True, null=True)
    skills = models.CharField(max_length=200, blank=True, null=True)


    def __str__(self):
        return self.user.username

