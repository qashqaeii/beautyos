from django.urls import path

from apps.appointments import views_public as booking_views
from apps.appointments import views_customer as customer_views
from apps.salons import views_public

app_name = "salons_public"

urlpatterns = [
    path("<str:slug>/", views_public.public_landing, name="landing"),
    path("<str:slug>/my/", customer_views.customer_home, name="customer_home"),
    path("<str:slug>/my/login/", customer_views.customer_login, name="customer_login"),
    path("<str:slug>/my/verify/", customer_views.customer_verify, name="customer_verify"),
    path("<str:slug>/my/logout/", customer_views.customer_logout, name="customer_logout"),
    path("<str:slug>/my/appointments/<int:appointment_id>/", customer_views.customer_appointment, name="customer_appointment"),
    path("<str:slug>/my/appointments/<int:appointment_id>/cancel/", customer_views.customer_cancel, name="customer_cancel"),
    path("<str:slug>/my/appointments/<int:appointment_id>/reschedule/", customer_views.customer_reschedule, name="customer_reschedule"),
    path("<str:slug>/book/", booking_views.booking_start, name="booking_start"),
    path("<str:slug>/book/staff/", booking_views.booking_staff, name="booking_staff"),
    path("<str:slug>/book/slot/", booking_views.booking_pick_slot, name="booking_pick_slot"),
    path("<str:slug>/book/datetime/", booking_views.booking_datetime, name="booking_datetime"),
    path("<str:slug>/book/contact/", booking_views.booking_contact, name="booking_contact"),
    path("<str:slug>/book/verify/", booking_views.booking_verify, name="booking_verify"),
    path("<str:slug>/book/confirm/", booking_views.booking_confirm, name="booking_confirm"),
]
