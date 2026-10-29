import os
import sys
import django

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Quiz.settings')
django.setup()

from Quizapp.models import CustomUser

print("Users and their passwords:")
for u in CustomUser.objects.all()[:10]:
    print(f"Email: {u.email}, Password: {u.password}, check('anything'): {u.check_password('anything')}")
