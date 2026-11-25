"""Chromium E2E for receptionist invoice creation and printable copy (mobile/desktop)."""
from urllib.parse import urlsplit

import pytest
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from apps.appointments.services.confirmation import confirm_pending_appointment
from apps.appointments.services.lifecycle import complete_appointment
from tests.test_phase5_daily_operations import day_case  # noqa: F401

pw = pytest.importorskip("playwright.sync_api")


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("width,height", [(375, 812), (1366, 768)])
def test_reception_creates_invoice_and_exposes_print_on_same_day(
    live_server, client, salon, owner_membership, day_case, width, height,
):
    customer, _, _, appointment, day = day_case
    confirm_pending_appointment(salon=salon, appointment_id=appointment.pk)
    complete_appointment(salon=salon, appointment_id=appointment.pk)
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.pk)
    session.save()
    cookie = client.cookies[settings.SESSION_COOKIE_NAME].value

    with pw.sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": width, "height": height},
            locale="fa-IR", reduced_motion="reduce",
        )
        context.add_cookies([{
            "name": settings.SESSION_COOKIE_NAME,
            "value": cookie,
            "url": live_server.url,
        }])
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
        page.on("pageerror", lambda e: errors.append(str(e)))
        desk = reverse("reception:desk") + "?day=" + day.isoformat()
        response = page.goto(live_server.url + desk, wait_until="load")
        assert response and response.status == 200
        assert page.get_by_role("heading", name="میز پذیرش").is_visible()
        assert page.get_by_role("link", name="فاکتورهای صادرشده").is_visible()
        page.locator(".reception-operations-disclosure > summary").click()
        invoice = page.locator(".reception-flow__invoice-panel")
        assert invoice.count() == 1
        invoice.locator("summary").click()
        assert invoice.locator('input[name="cash"]').is_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 3")
        invoice.locator('input[name="card"]').fill("800000")
        invoice.get_by_role("button", name="فقط ثبت فاکتور").click()
        page.wait_for_url("**/invoices/*/")
        assert page.locator(".checkout-workspace--issued").is_visible()
        assert page.get_by_role("button", name="چاپ / ذخیره PDF").is_visible()

        page.goto(live_server.url + desk, wait_until="load")
        page.locator(".reception-operations-disclosure > summary").click()
        assert page.get_by_role("link", name="چاپ فاکتور " + customer.full_name).is_visible()
        assert page.locator(".reception-flow__invoice-panel").count() == 0
        print_link = page.get_by_role("link", name="چاپ فاکتور " + customer.full_name)
        assert print_link.get_attribute("href").endswith("?print=1")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 3")
        assert not external, external
        assert not errors, errors
        context.close()
        browser.close()
