from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.timezone import now
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from django.conf import settings

User = get_user_model()


# ------------------------------------------
# Request Password Reset Email
# ------------------------------------------
class PasswordResetRequestView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        username = request.data.get("username")

        if not username:
            return Response({"detail": "Username is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response({"detail": "No user found with that username."}, status=status.HTTP_404_NOT_FOUND)

        # generate uid and token
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        # frontend password reset link
        reset_link = f"{settings.FRONTEND_URL}/reset-password/{uid}/{token}/"

        # render HTML email with theme
        html_message = render_to_string(
            "emails/../templates/emails/password_reset.html",
            {
                "user": user,
                "reset_link": reset_link,
                "year": now().year,
            },
        )

        # fallback plain text
        plain_message = f"Hi {user.username},\n\nUse this link to reset your password:\n{reset_link}"

        send_mail(
            subject="Password Reset Request",
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )

        return Response(
            {"detail": "Password reset email sent."},
            status=status.HTTP_200_OK,
        )


# ------------------------------------------
# Confirm Password Reset (New Password)
# ------------------------------------------
class PasswordResetConfirmView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        uidb64 = request.data.get("uid")
        token = request.data.get("token")
        new_password = request.data.get("new_password")

        if not uidb64 or not token or not new_password:
            return Response({"detail": "Invalid request."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (User.DoesNotExist, ValueError, TypeError):
            return Response({"detail": "Invalid user or token."}, status=status.HTTP_400_BAD_REQUEST)

        if not default_token_generator.check_token(user, token):
            return Response({"detail": "Token is invalid or expired."}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()

        return Response({"detail": "Password reset successful."}, status=status.HTTP_200_OK)
