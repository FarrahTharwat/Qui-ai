import os
from celery import Celery

# Set the default Django settings module for the Celery program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "notifications_project.settings")

app = Celery("notifications_project")

# Load task modules from all registered Django app configs.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks in Django apps
app.autodiscover_tasks()

# Ensure Celery can use Django ORM
app.conf.update(
    task_annotations={"*": {"rate_limit": "10/s"}}
)
