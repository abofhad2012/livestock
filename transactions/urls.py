from django.urls import path
from . import views

app_name = "transactions"

urlpatterns = [
    # عمليات
    path("api/purchase/", views.api_purchase, name="api_purchase"),
    path("api/sale/", views.api_sale, name="api_sale"),
    # سداد لاحق (تحصيل فعلي)
    path("api/payment/add/", views.api_payment_add, name="api_payment_add"),
    # إلغاء / مرتجع
    path("api/tx/<int:tx_id>/cancel/", views.api_tx_cancel, name="api_tx_cancel"),
    path("api/tx/<int:tx_id>/return/", views.api_tx_return, name="api_tx_return"),
    # مخزون + عملاء
    path("api/stock/", views.api_stock, name="api_stock"),
    path("api/clients/search/", views.api_clients_search, name="api_clients_search"),
    # تحصيل / متأخرات
    path("api/ar/aging/", views.api_ar_aging, name="api_ar_aging"),
    path(
        "api/clients/<int:pk>/whatsapp-reminder/",
        views.api_client_whatsapp_reminder,
        name="api_client_whatsapp_reminder",
    ),
    # ✅ حالة العملاء (تم السداد / لم يتم السداد / متأخر + واتساب)
    path("api/ar/clients/summary/", views.api_ar_clients_summary, name="api_ar_clients_summary"),
]