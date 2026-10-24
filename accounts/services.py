from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from .models import Customer, User


def _raise_email_conflict(error):
    cause = error.__cause__
    if getattr(cause, "sqlstate", None) == "23505" and cause.diag.constraint_name in {
        "user_email_ci_unique",
        "accounts_user_email_key",
    }:
        raise ValidationError({"email": ["Email ja cadastrado."]}) from error
    raise error


def register_customer(*, email, name, password, phone=""):
    candidate = User(email=User.objects.normalize_email(email), name=name)
    try:
        validate_password(password, user=candidate)
    except ValidationError as error:
        raise ValidationError({"password": error.messages}) from error
    try:
        with transaction.atomic():
            user = User.objects.create_user(candidate.email, password, name=name)
            customer = Customer(user=user, phone=phone)
            customer.full_clean()
            customer.save()
            return user
    except IntegrityError as error:
        _raise_email_conflict(error)


def update_profile(*, user, email=None, name=None, phone=None):
    try:
        with transaction.atomic():
            # Rele a versao atual sob bloqueio; evita sobrescrever mudancas
            # concorrentes de senha, privilegios ou outros campos do perfil.
            current = User.objects.select_for_update().get(pk=user.pk)
            fields = []
            if email is not None:
                current.email = User.objects.normalize_email(email)
                fields.append("email")
            if name is not None:
                current.name = name
                fields.append("name")
            current.full_clean()
            if fields:
                current.save(update_fields=fields)
            if phone is not None:
                try:
                    customer = current.customer
                except Customer.DoesNotExist as error:
                    raise ValidationError({"phone": ["Conta sem perfil de cliente."]}) from error
                customer.phone = phone
                customer.full_clean()
                customer.save(update_fields=["phone", "updated_at"])
            return current
    except IntegrityError as error:
        _raise_email_conflict(error)
