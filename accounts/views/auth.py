# accounts/views/auth.py
from django.contrib.auth import authenticate, get_user_model
from rest_framework import status
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from ..serializers import UserSerializer

User = get_user_model()


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []  # allow tokenless

    def post(self, request, *args, **kwargs):
        username = request.data.get("username")
        password = request.data.get("password")
        if not username or not password:
            return Response({"detail": "username & password required"}, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(request, username=username, password=password)
        if not user:
            return Response({"detail": "invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)

        refresh = RefreshToken.for_user(user)
        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": UserSerializer(user, context={"request": request}).data,
        }, status=status.HTTP_200_OK)


class LogoutView(APIView):
    """
    Invalidate refresh token (blacklist). Expects {"refresh": "<token>"}.
    Requires rest_framework_simplejwt.token_blacklist app installed.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        token = request.data.get("refresh")
        if not token:
            return Response({"detail": "refresh token required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            RefreshToken(token).blacklist()
        except Exception:
            return Response({"detail": "invalid token"}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "logged out"}, status=status.HTTP_205_RESET_CONTENT)


class MeView(RetrieveUpdateAPIView):
    """
    GET  - returns the authenticated user's info
    PUT  - updates user profile fields (first_name, last_name, etc.)
    PATCH - partial update
    """
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user