"""Offline-first RTL Chromium smoke for customer portal at mobile and desktop sizes."""
from urllib.parse import urlsplit

import pytest
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from apps.appointments.customer_portal import ACCESS_SESSION_KEY
from apps.appointments.models import Appointment
from apps.customers.models import Customer
from tests.test_public_booking_flow import public_booking_setup  # noqa: F401

pw = pytest.importorskip("playwright.sync_api")


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("width,height", [(375, 812), (1366, 768)])
def test_customer_portal_responsive_no_external_assets(
    live_server, client, salon, public_booking_setup, width, height,
):
    data = public_booking_setup
    customer = Customer.objects.create(salon=salon, phone=data["phone"], full_name="سارا مشتری")
    appt = Appointment.objects.create(
        salon=salon, customer=customer, staff=data["staff"], service=data["service"],
        start_at=timezone.datetime.fromisoformat(data["start_iso"]),
        end_at=timezone.datetime.fromisoformat(data["start_iso"]) + timezone.timedelta(minutes=30),
        source=Appointment.Source.PUBLIC, status=Appointment.Status.CONFIRMED,
    )
    with pw.sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": width, "height": height}, locale="fa-IR",
            reduced_motion="reduce",
        )
        origin = urlsplit(live_server.url).netloc
        external = []
        def local_only(route):
            if urlsplit(route.request.url).netloc != origin:
                external.append(route.request.url)
                route.abort()
            else:
                route.continue_()
        context.route("**/*", local_only)
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        login = reverse("salons_public:customer_login", kwargs={"slug": salon.slug})
        assert page.goto(live_server.url + login, wait_until="load").status == 200
        assert page.get_by_role("heading", name="نوبت‌ها همیشه در دسترس شما").is_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 3")

        session = client.session
        session[ACCESS_SESSION_KEY] = {
            "salon_id": str(salon.pk), "phone": data["phone"],
            "verified_at": int(timezone.now().timestamp()),
        }
        session.save()
        context.add_cookies([{
            "name": settings.SESSION_COOKIE_NAME,
            "value": client.cookies[settings.SESSION_COOKIE_NAME].value,
            "url": live_server.url,
        }])
        routes = [
            reverse("salons_public:customer_home", kwargs={"slug": salon.slug}),
            reverse("salons_public:customer_appointment", kwargs={
                "slug": salon.slug, "appointment_id": appt.pk,
            }),
            reverse("salons_public:customer_reschedule", kwargs={
                "slug": salon.slug, "appointment_id": appt.pk,
            }),
        ]
        for route in routes:
            resp = page.goto(live_server.url + route, wait_until="load")
            assert resp and resp.status == 200, route
            assert page.locator("html").get_attribute("dir") == "rtl", route
            assert page.locator(".cp-intro h1").count() == 1, route
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 3"), route
            assert page.locator('meta[name="robots"]').get_attribute("content") == "noindex,nofollow"
        assert page.get_by_role("heading", name="انتخاب زمان جدید").is_visible()
        assert not external, external
        assert not errors, errors
        context.close()
        browser.close()
