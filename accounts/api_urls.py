from django.urls import path

from . import api_views

app_name = "api_auth"

urlpatterns = [
    path("register/", api_views.register, name="register"),
    path("login/", api_views.login, name="login"),
    path("logout/", api_views.logout, name="logout"),
    path("me/", api_views.me, name="me"),
]
