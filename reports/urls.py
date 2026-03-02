from django.urls import path
from . import views

app_name = "reports"

urlpatterns = [
    path("summary/", views.summary, name="summary"),
    path("summary/pdf/", views.summary_pdf, name="summary_pdf"),
    path("tx/<int:tx_id>/", views.tx_preview, name="tx_preview"),
    path("tx/<int:tx_id>/pdf/", views.tx_pdf, name="tx_pdf"),

    # ✅ جديد
    path("analytics/", views.analytics, name="analytics"),
]