from rest_framework.permissions import BasePermission

from .models import Customer


def is_store_admin(user):
    return bool(user and user.is_authenticated and user.is_active and user.is_staff)


def is_customer(user):
    return bool(
        user
        and user.is_authenticated
        and user.is_active
        and not user.is_staff
        and Customer.objects.filter(user_id=user.pk).exists()
    )


class IsCustomer(BasePermission):
    def has_permission(self, request, view):
        return is_customer(request.user)


class IsStoreAdmin(BasePermission):
    def has_permission(self, request, view):
        return is_store_admin(request.user)


class CanReadOrder(BasePermission):
    """Leitura somente; nao concede permissoes para mudar estado ou estoque."""

    def has_permission(self, request, view):
        return request.method in ("GET", "HEAD", "OPTIONS") and (
            is_store_admin(request.user) or is_customer(request.user)
        )

    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view) and (
            is_store_admin(request.user) or obj.customer.user_id == request.user.pk
        )
