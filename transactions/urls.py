from django.urls import path
from . import views

app_name = "transactions"

urlpatterns = [
    path("api/purchase/", views.api_purchase, name="api_purchase"),
    path("api/sale/", views.api_sale, name="api_sale"),

    # ✅ الرصيد (لإظهار المخزون قبل الحفظ)
    path("api/stock/", views.api_stock, name="api_stock"),

    # ✅ بحث العملاء بالجوال/الاسم (للداتاليست)
    path("api/clients/search/", views.api_clients_search, name="api_clients_search"),
]