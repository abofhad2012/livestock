from django.urls import path

from . import api_views

app_name = "api_transactions"

urlpatterns = [
    path("stock/", api_views.stock, name="stock"),
    path("purchase/", api_views.purchase, name="purchase"),
    path("sale/", api_views.sale, name="sale"),
]
