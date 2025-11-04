# FILE: accounts/tasks.py
from celery import shared_task
from django.core.mail import send_mail
from django.contrib.auth import get_user_model

User = get_user_model()


@shared_task
def send_welcome_email(user_id):
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return False
    send_mail(
        subject="Welcome to lmanagement",
        message=f"Hello {user.first_name or user.username}, welcome!",
        from_email=None,
        recipient_list=[user.email],
    )
    return True
