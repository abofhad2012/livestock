"""
URL configuration for livestock project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

# ✅ تخصيص عناوين لوحة التحكم
admin.site.site_header = "المواشي - لوحة التحكم"
admin.site.site_title = "المواشي"
admin.site.index_title = "إدارة الموقع"

urlpatterns = [
    path("admin/", admin.site.urls),

    # الصفحة الرئيسية من template مباشرة
    path("", TemplateView.as_view(template_name="home.html"), name="home"),

    # التطبيقات (حتى لو urls.py فاضية حالياً)
    path("accounts/", include("accounts.urls")),
    path("herd/", include("herd.urls")),
    path("transactions/", include("transactions.urls")),
    path("reports/", include("reports.urls")),
]

# ✅ عرض ملفات media أثناء التطوير فقط
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)