from django.urls import path

from apps.finance import views

app_name = "finance"

urlpatterns = [
    path("", views.finance_overview, name="overview"),
    path("payments/new/", views.payment_create, name="payment_create"),
    path("payments/<int:payment_id>/receipt/", views.payment_receipt, name="receipt"),
]
