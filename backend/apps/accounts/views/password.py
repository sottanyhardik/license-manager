import logging

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.timezone import now
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.throttling import ScopedRateThrottle
from django.conf import settings
from django.db.models import Q

User = get_user_model()
logger = logging.getLogger(__name__)

# Uniform response so the endpoint never reveals whether an account exists.
_GENERIC_RESET_MESSAGE = "If an account matches that email or username, a password reset link has been sent."


# ------------------------------------------
# Request Password Reset Email
# ------------------------------------------
class PasswordResetRequestView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    def post(self, request, *args, **kwargs):
        identifier = (request.data.get("email") or request.data.get("username") or "").strip()

        if not identifier:
            return Response({"detail": "Email or username is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Look the user up, but ALWAYS return the same generic response and status
        # regardless of whether the account (or its email) exists — otherwise the
        # endpoint leaks which usernames/emails are registered (user enumeration).
        user = User.objects.filter(
            Q(email__iexact=identifier) | Q(username__iexact=identifier)
        ).first()

        if user and user.email:
            try:
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                token = default_token_generator.make_token(user)
                reset_link = f"{settings.FRONTEND_URL}/reset-password/{uid}/{token}/"
                html_message = render_to_string(
                    "emails/password_reset.html",
                    {"user": user, "reset_link": reset_link, "year": now().year},
                )
                plain_message = f"Hi {user.username},\n\nUse this link to reset your password:\n{reset_link}"
                send_mail(
                    subject="Password Reset Request",
                    message=plain_message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    html_message=html_message,
                    fail_silently=False,
                )
            except Exception:
                # Never surface send failures to the caller (would leak existence
                # via a differing error). Log for ops instead.
                logger.exception("Password reset email failed for identifier=%r", identifier)

        return Response({"detail": _GENERIC_RESET_MESSAGE}, status=status.HTTP_200_OK)


# ------------------------------------------
# Confirm Password Reset (New Password)
# ------------------------------------------
class PasswordResetConfirmView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

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

        # Enforce the configured AUTH_PASSWORD_VALIDATORS on the new password —
        # previously any password (even "1") was accepted on the reset path.
        try:
            validate_password(new_password, user)
        except DjangoValidationError as exc:
            return Response({"detail": exc.messages}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()

        return Response({"detail": "Password reset successful."}, status=status.HTTP_200_OK)
