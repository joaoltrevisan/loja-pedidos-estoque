from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from common.views import PrivateResponseMixin

from .serializers import (
    ActiveUserRefreshSerializer,
    LoginSerializer,
    ProfileSerializer,
    ProfileUpdateSerializer,
    RegistrationSerializer,
)


class RegistrationView(PrivateResponseMixin, APIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)
    throttle_scope = "register"

    def post(self, request):
        serializer = RegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(ProfileSerializer(user).data, status=status.HTTP_201_CREATED)


class LoginView(PrivateResponseMixin, TokenObtainPairView):
    serializer_class = LoginSerializer
    throttle_scope = "login"


class RefreshView(PrivateResponseMixin, TokenRefreshView):
    serializer_class = ActiveUserRefreshSerializer
    throttle_scope = "refresh"


class ProfileView(PrivateResponseMixin, APIView):
    throttle_scope = "profile"

    def get(self, request):
        return Response(ProfileSerializer(request.user).data)

    def patch(self, request):
        serializer = ProfileUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(ProfileSerializer(user).data)
