from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView, TemplateView

admin.site.site_header = "المواشي - لوحة التحكم"
admin.site.site_title = "المواشي"
admin.site.index_title = "إدارة الموقع"

urlpatterns = [
    path("admin/", admin.site.urls),

    path("", TemplateView.as_view(template_name="home.html"), name="home"),

    path("accounts/", include("accounts.urls")),
    path("herd/", include("herd.urls")),
    path("transactions/", include("transactions.urls")),
    path("reports/", include("reports.urls")),

    path(
        "favicon.ico",
        RedirectView.as_view(url=settings.STATIC_URL + "favicon.ico", permanent=False),
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)