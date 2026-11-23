"""Real Chromium responsive public site and salon storefront smoke tests."""
from urllib.parse import urlsplit

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.website.models import BlogPost

pw = pytest.importorskip("playwright.sync_api")


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("width,height", [(390, 844), (1366, 768)])
def test_public_v3_pages_are_responsive_and_offline_first(
    live_server, salon, width, height
):
    article = BlogPost.objects.create(
        title="مراقبت از سالن زیبایی زنانه", slug="salon-care-guide",
        summary="راهنمای مدیریت مشتریان و خدمات سالن",
        body="متن مقاله راهنما برای مدیران سالن.",
        status=BlogPost.Status.PUBLISHED, published_at=timezone.now(),
    )
    pages = [
        reverse("website:home"), reverse("website:features"),
        reverse("website:blog"),
        reverse("website:blog_post", kwargs={"slug": article.slug}),
        reverse("website:faq"), reverse("website:contact"),
        reverse("website:privacy"), reverse("website:terms"),
        reverse("salons_public:landing", kwargs={"slug": salon.slug}),
    ]
    with pw.sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": width, "height": height},
            locale="fa-IR", reduced_motion="reduce",
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
        js_errors = []
        page.on("pageerror", lambda error: js_errors.append(str(error)))
        for url in pages:
            response = page.goto(live_server.url + url, wait_until="load")
            assert response and response.status == 200, url
            assert page.locator("html").get_attribute("dir") == "rtl", url
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 3"), url
            assert page.locator('link[rel="canonical"]').count() == 1, url
        page.goto(live_server.url + reverse("website:blog"), wait_until="load")
        assert page.locator(".pub3-blog-card").count() == 1
        page.get_by_label("جستجو در مقالات").fill("مراقبت")
        page.get_by_role("button", name="جستجو").click()
        assert "q=" in page.url
        assert page.locator(".pub3-blog-card").count() == 1
        page.goto(live_server.url + reverse("website:contact"), wait_until="load")
        assert page.locator("form.pub3-contact-form input[name='name']").is_visible()
        assert page.locator("form.pub3-contact-form textarea[name='message']").is_visible()
        page.goto(live_server.url + reverse("salons_public:landing", kwargs={"slug": salon.slug}), wait_until="load")
        assert page.locator(".pub3-salon__hero").count() == 1
        if width < 650 and salon.is_accepting_bookings:
            assert page.locator(".pub3-salon__mobile-book").is_visible()
        assert not external, external
        assert not js_errors, js_errors
        context.close()
        browser.close()
