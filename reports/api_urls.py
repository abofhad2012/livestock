from django.urls import path

from . import api_views

app_name = "api_reports"

urlpatterns = [
    path("summary/", api_views.summary, name="summary"),
]
