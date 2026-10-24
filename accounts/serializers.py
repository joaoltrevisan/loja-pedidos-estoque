from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.crypto import constant_time_compare
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.utils import get_md5_hash_password

from common.serializers import StrictInputMixin, TextField

from .authentication import token_user_id
from .models import Customer, User
from .services import register_customer, update_profile


def validation_detail(error):
    return error.message_dict if hasattr(error, "message_dict") else {"detail": error.messages}


class ProfileSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    email = serializers.EmailField(read_only=True)
    name = serializers.CharField(read_only=True)
    phone = serializers.SerializerMethodField()
    role = serializers.SerializerMethodField()

    def get_phone(self, user):
        try:
            return user.customer.phone
        except Customer.DoesNotExist:
            return None

    def get_role(self, user):
        if user.is_staff:
            return "administrator"
        return "customer" if hasattr(user, "customer") else "unassigned"


class RegistrationSerializer(StrictInputMixin, serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    name = TextField(max_length=150)
    password = TextField(write_only=True, trim_whitespace=False, max_length=128)
    phone = TextField(max_length=20, allow_blank=True, required=False)

    def create(self, validated_data):
        try:
            return register_customer(**validated_data)
        except DjangoValidationError as error:
            raise serializers.ValidationError(validation_detail(error)) from error


class ProfileUpdateSerializer(StrictInputMixin, serializers.Serializer):
    email = serializers.EmailField(max_length=254, required=False)
    name = TextField(max_length=150, required=False)
    phone = TextField(max_length=20, allow_blank=True, required=False)

    def update(self, instance, validated_data):
        try:
            return update_profile(user=instance, **validated_data)
        except DjangoValidationError as error:
            raise serializers.ValidationError(validation_detail(error)) from error


class LoginSerializer(StrictInputMixin, TokenObtainPairSerializer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"] = serializers.EmailField(max_length=254, write_only=True)
        self.fields["password"] = TextField(write_only=True, trim_whitespace=False, max_length=128)


class ActiveUserRefreshSerializer(StrictInputMixin, TokenRefreshSerializer):
    refresh = TextField(write_only=True, max_length=4096, trim_whitespace=False)

    def validate(self, attrs):
        # Mantem assinatura, prazo e tipo validados pela biblioteca. O refresh
        # 5.5.1 nao trata usuario removido e nao verifica revogacao por senha.
        refresh = self.token_class(attrs["refresh"])
        try:
            user = User.objects.get(pk=token_user_id(refresh))
        except User.DoesNotExist as error:
            raise AuthenticationFailed("Credencial invalida.") from error
        if not api_settings.USER_AUTHENTICATION_RULE(user) or not constant_time_compare(
            str(refresh.get(api_settings.REVOKE_TOKEN_CLAIM, "")),
            get_md5_hash_password(user.password),
        ):
            raise AuthenticationFailed("Credencial invalida.")
        # Renovacao sem rotacao: a validade original do refresh nao se estende.
        return {"access": str(refresh.access_token)}
