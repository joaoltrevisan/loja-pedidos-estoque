from django.urls import path

from .views import LoginView, ProfileView, RefreshView, RegistrationView

app_name = "accounts"
urlpatterns = [
    path("register/", RegistrationView.as_view(), name="register"),
    path("token/", LoginView.as_view(), name="token"),
    path("token/refresh/", RefreshView.as_view(), name="refresh"),
    path("me/", ProfileView.as_view(), name="me"),
]
