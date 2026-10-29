import os
import sys
import django

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Quiz.settings')
django.setup()

from Quizapp.models import CustomUser

user = CustomUser.objects.first()
if user:
    print(f"User: {user.email}")
    print(f"Hashed password: {user.password}")
    print(f"check_password('wrong_password'): {user.check_password('wrong_password')}")
    print(f"check_password(''): {user.check_password('')}")
else:
    print("No users found.")
