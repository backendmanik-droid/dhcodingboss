import os
from celery import Celery

# Tell Celery which Django settings module to use
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Quiz.settings")

app = Celery("Quiz")

# Read Celery config from Django settings (keys prefixed with CELERY_)
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks in all installed apps (looks for tasks.py in each app)
app.autodiscover_tasks()
