from django.urls import path

from apps.finance import views, checkout_views, cash_close

app_name = "finance"

urlpatterns = [
    path("", views.finance_overview, name="overview"),
    path("cash-close/", cash_close.cash_close_view, name="cash_close"),
    path("checkout/", checkout_views.checkout_customers, name="checkout_customers"),
    path("checkout/<int:customer_id>/", checkout_views.checkout, name="checkout"),
    path("invoices/", checkout_views.invoice_list, name="invoices"),
    path("invoices/<int:invoice_id>/", checkout_views.invoice_detail, name="invoice_detail"),
    path("payments/new/", views.payment_create, name="payment_create"),
    path("payments/<int:payment_id>/receipt/", views.payment_receipt, name="receipt"),
]
