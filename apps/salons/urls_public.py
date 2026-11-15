from django.urls import path

from apps.appointments import views_public as booking_views
from apps.salons import views_public

app_name = "salons_public"

urlpatterns = [
    path("<str:slug>/", views_public.public_landing, name="landing"),
    path("<str:slug>/book/", booking_views.booking_start, name="booking_start"),
    path("<str:slug>/book/staff/", booking_views.booking_staff, name="booking_staff"),
    path("<str:slug>/book/slot/", booking_views.booking_pick_slot, name="booking_pick_slot"),
    path("<str:slug>/book/datetime/", booking_views.booking_datetime, name="booking_datetime"),
    path("<str:slug>/book/contact/", booking_views.booking_contact, name="booking_contact"),
    path("<str:slug>/book/verify/", booking_views.booking_verify, name="booking_verify"),
    path("<str:slug>/book/confirm/", booking_views.booking_confirm, name="booking_confirm"),
]
