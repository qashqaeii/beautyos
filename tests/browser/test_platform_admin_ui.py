"""Chromium smoke coverage for the independent platform control center."""
from urllib.parse import urlsplit

import pytest
from django.conf import settings
from django.urls import reverse

from apps.accounts.models import User
from apps.platform_admin.models import SupportTicket

pw = pytest.importorskip("playwright.sync_api")


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("width,height", [(375, 812), (1366, 768)])
def test_platform_control_center_responsive_and_private(
    live_server, client, owner_membership, width, height
):
    operator = User.objects.create_superuser(
        phone="+989101010017", full_name="مدیر مرکزی",
        password="platform-browser-only-password",
    )
    SupportTicket.objects.create(
        salon=owner_membership.salon,
        opened_by=owner_membership.user,
        title="پشتیبانی رزرو آنلاین",
    )
    client.force_login(operator)
    with pw.sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": width, "height": height},
            locale="fa-IR", reduced_motion="reduce",
        )
        context.add_cookies([{
            "name": settings.SESSION_COOKIE_NAME,
            "value": client.cookies[settings.SESSION_COOKIE_NAME].value,
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
        routes = [
            reverse("platform_admin:overview"),
            reverse("platform_admin:salons"),
            reverse("platform_admin:users"),
            reverse("platform_admin:reports"),
            reverse("platform_admin:subscriptions"),
            reverse("platform_admin:support"),
            reverse("platform_admin:articles"),
            reverse("platform_admin:article_new"),
            reverse("platform_admin:audit"),
            reverse("platform_admin:system"),
            reverse("platform_admin:salon_detail", kwargs={"salon_id": owner_membership.salon_id}),
            reverse("platform_admin:user_detail", kwargs={"user_id": operator.pk}),
        ]
        for route in routes:
            response = page.goto(live_server.url + route, wait_until="load")
            assert response and response.status == 200, route
            assert page.locator(".pc-heading h1").count() == 1, route
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 3"), route
            assert page.locator("html").get_attribute("dir") == "rtl"
            assert page.locator('link[href*="beautyos-motion.css"]').count() == 1
            assert page.locator('script[src*="beautyos-motion.js"]').count() == 1
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 3")

            assert page.locator('link[href*="phase7-ui-polish.css"]').count() == 1
        page.goto(live_server.url + reverse("platform_admin:subscriptions"), wait_until="load")
        assert page.locator(".pc-subscriptions__filter select").count() == 1
        assert page.locator(".pc-subscriptions__filter label").is_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 3")
        page.goto(live_server.url + reverse("platform_admin:overview"), wait_until="load")
        # CI normally requests reduced motion; no movement or counter rewrite is allowed.
        assert page.evaluate("matchMedia('(prefers-reduced-motion: reduce)').matches")
        card = page.locator(".pc-kpi").first
        if card.count():
            assert card.evaluate("(el) => getComputedStyle(el).translate === 'none' || getComputedStyle(el).translate === '0px'")
            before = card.locator("strong").first.inner_text()
            page.wait_for_timeout(100)
            assert card.locator("strong").first.inner_text() == before

        if width < 960:
            page.locator(".pc-mobile-menu summary").click()
            assert page.locator(".pc-mobile-menu nav").is_visible()
            page.locator(".pc-mobile-menu nav a").filter(has_text="سالن‌ها").click()
            assert page.url.endswith(reverse("platform_admin:salons"))
        else:
            assert page.locator(".pc-sidebar").is_visible()
        assert not external, external
        assert not errors, errors
        context.close()
        browser.close()
