from django.urls import path

from apps.finance import views, checkout_views, cash_close, ledger_views, period_views, stock_views

app_name = "finance"

urlpatterns = [
    path("", views.finance_overview, name="overview"),
    path("reports/export/", views.export_report, name="export_report"),
    path("accounts/", ledger_views.accounts_view, name="accounts"),
    path("product-sales/", stock_views.product_sales, name="product_sales"),
    path("product-sales/<int:sale_id>/return/", stock_views.product_return, name="product_return"),
    path("materials/", stock_views.materials, name="materials"),
    path("staff-finance/", period_views.staff_finance, name="staff_finance"),
    path("recurring/", period_views.recurring_expenses, name="recurring"),
    path("payments/<int:payment_id>/refund/", ledger_views.refund_view, name="refund"),
    path("cash-close/", cash_close.cash_close_view, name="cash_close"),
    path("checkout/", checkout_views.checkout_customers, name="checkout_customers"),
    path("checkout/<int:customer_id>/", checkout_views.checkout, name="checkout"),
    path("invoices/", checkout_views.invoice_list, name="invoices"),
    path("invoices/<int:invoice_id>/", checkout_views.invoice_detail, name="invoice_detail"),
    path("payments/new/", views.payment_create, name="payment_create"),
    path("payments/<int:payment_id>/receipt/", views.payment_receipt, name="receipt"),
]
