"""Public V3: SEO, safe publishing, tenant storefronts, and contact anti-abuse."""
from datetime import timedelta

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.salons.models import Salon, SalonSettings, SalonWorkHours
from apps.services.models import Service
from apps.staff.models import StaffProfile
from apps.website.models import BlogPost, ContactInquiry


def _article(title, slug, *, status="published", category="راهنما", summary="خلاصه مفید"):
    return BlogPost.objects.create(
        title=title, slug=slug, body="مطالب کاربردی و توضیحات کامل",
        status=status, category=category, summary=summary,
        published_at=timezone.now() if status == "published" else None,
    )


@pytest.mark.django_db
def test_public_pages_offer_unique_canonical_metadata(client):
    cases = [
        ("website:home", "website:home"),
        ("website:features", "website:features"),
        ("website:blog", "website:blog"),
        ("website:faq", "website:faq"),
        ("website:contact", "website:contact"),
        ("website:privacy", "website:privacy"),
        ("website:terms", "website:terms"),
    ]
    for route, canonical in cases:
        response = client.get(reverse(route))
        content = response.content.decode()
        assert response.status_code == 200
        assert content.count('rel="canonical"') == 1
        assert reverse(canonical) in content
        assert 'property="og:title"' in content
        assert 'name="description"' in content
        assert 'name="robots" content="index,follow"' in content


@pytest.mark.django_db
def test_blog_search_filters_pagination_and_no_draft_leaks(client):
    for i in range(14):
        _article(f"مراقبت مو {i}", f"hair-care-{i}", category="مو")
    for i in range(4):
        _article(f"خدمات ناخن {i}", f"nails-{i}", category="ناخن")
    _article("مقاله خصوصی", "private", status="draft")
    url = reverse("website:blog")

    page = client.get(url)
    assert page.status_code == 200
    assert page.context["results_count"] == 18
    assert len(page.context["posts"]) == 9
    assert page.context["page_obj"].has_next()
    second = client.get(url + "?page=2")
    assert len(second.context["posts"]) == 9

    search = client.get(url, {"q": "ناخن"})
    assert search.context["results_count"] == 4
    assert 'content="noindex,follow"' in search.content.decode()
    selected = client.get(url, {"category": "مو", "q": "مراقبت"})
    assert selected.context["results_count"] == 14
    none = client.get(url, {"q": "مقاله خصوصی"})
    assert none.context["results_count"] == 0
    assert "pub3-blog-card" not in none.content.decode()


@pytest.mark.django_db
def test_persian_article_slug_and_json_ld_are_safe(client):
    post = _article('راهنمای فارسی </script><script>alert(1)</script>',
                    "راهنمای-فارسی", summary="یک نوشته آموزشی")
    post.body = "متن امن </script><script>alert(1)</script>"
    post.save(update_fields=["body", "updated_at"])
    response = client.get(reverse("website:blog_post", kwargs={"slug": post.slug}))
    assert response.status_code == 200
    rendered = response.content.decode()
    assert 'type="application/ld+json"' in rendered
    assert "schema.org" in rendered
    assert 'rel="canonical"' in rendered
    assert post.slug == response.context["post"].slug
    assert reverse("website:blog_post", kwargs={"slug": post.slug}) in rendered
    assert '</script><script>alert(1)</script>' not in rendered
    assert "&lt;script&gt;" in rendered
    assert response.context["reading_minutes"] >= 1
    assert client.get(reverse("website:blog_post", kwargs={"slug": "missing"})).status_code == 404


@pytest.mark.django_db
def test_sitemap_excludes_unpublished_content_and_unready_salons(client, salon):
    published = _article("مقاله منتشرشده", "visible-article")
    _article("پیش‌نویس", "hidden-draft", status="draft")
    not_ready = Salon.objects.create(name="سالن در حال تکمیل", is_accepting_bookings=False)
    SalonSettings.objects.create(salon=not_ready)
    salon.is_accepting_bookings = True
    salon.save(update_fields=["is_accepting_bookings"])
    response = client.get(reverse("website:sitemap"))
    assert response.status_code == 200
    assert "xml" in response["Content-Type"]
    xml = response.content.decode()
    assert "visible-article" in xml
    assert "hidden-draft" not in xml
    assert reverse("salons_public:landing", kwargs={"slug": salon.slug}) in xml
    assert reverse("salons_public:landing", kwargs={"slug": not_ready.slug}) not in xml

    salon.is_accepting_bookings = False
    salon.save(update_fields=["is_accepting_bookings"])
    assert reverse("salons_public:landing", kwargs={"slug": salon.slug}) not in client.get(reverse("website:sitemap")).content.decode()


@pytest.mark.django_db
def test_robots_blocks_sensitive_routes_and_references_sitemap(client):
    response = client.get(reverse("website:robots"))
    assert response.status_code == 200
    robots = response.content.decode()
    assert "Disallow: /control/" in robots
    assert "Disallow: /s/*/book/" in robots
    assert "/sitemap.xml" in robots


@pytest.mark.django_db
def test_salon_storefront_respects_tenant_public_data_and_booking_state(
    client, owner_membership
):
    salon = owner_membership.salon
    service = Service.objects.create(
        salon=salon, name="مراقبت پوست", duration_minutes=60,
        price_toman=650000, is_active=True, is_public=True,
    )
    Service.objects.create(
        salon=salon, name="خدمت غیرعمومی", duration_minutes=30,
        is_public=False,
    )
    specialist = StaffProfile.objects.create(
        salon=salon, membership=owner_membership,
        display_name="نگین ساعی", title="متخصص پوست",
        is_active=True, is_bookable=True,
    )
    specialist.services.add(service)
    SalonWorkHours.objects.create(
        salon=salon, weekday=0, start_time="09:00", end_time="18:00",
    )
    salon.instagram = "beauty.salon"
    salon.whatsapp = "09121112233"
    salon.is_accepting_bookings = True
    salon.save(update_fields=["instagram", "whatsapp", "is_accepting_bookings"])
    url = reverse("salons_public:landing", kwargs={"slug": salon.slug})
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert 'class="pub3-salon ' in content
    assert "مراقبت پوست" in content
    assert "خدمت غیرعمومی" not in content
    assert "نگین ساعی" in content
    assert "650.000" in content or "۶۵۰.۰۰۰" in content
    assert "https://www.instagram.com/beauty.salon/" in content
    assert "https://wa.me/989121112233" in content
    assert 'content="index,follow"' in content

    salon.is_accepting_bookings = False
    salon.instagram = "javascript:alert(1)"
    salon.save(update_fields=["is_accepting_bookings", "instagram"])
    blocked = client.get(url).content.decode()
    assert 'content="noindex,follow"' in blocked
    assert "رزرو آنلاین غیرفعال" in blocked
    assert "javascript:alert" not in blocked

    salon.public_theme = Salon.PublicTheme.MINIMAL_STUDIO
    salon.save(update_fields=["public_theme"])
    neutral = client.get(url).content.decode()
    assert "pub3-salon--minimal" in neutral
    assert "آرایشگاه مردانه" not in neutral


@pytest.mark.django_db
def test_public_contact_validates_consent_and_records_minimal_information(client):
    url = reverse("website:contact")
    data = {
        "name": "آرزو احمدی", "phone": "09121112233",
        "email": "", "topic": "start",
        "message": "برای راه‌اندازی سالن نیاز به راهنمایی دارم.",
        "consent": "on",
    }
    assert client.get(url).status_code == 200
    assert ContactInquiry.objects.count() == 0
    missing_consent = {**data, "consent": ""}
    rejected = client.post(url, missing_consent)
    assert rejected.status_code == 200
    assert ContactInquiry.objects.count() == 0

    successful = client.post(url, data)
    assert successful.status_code == 302
    assert successful.url == url
    inquiry = ContactInquiry.objects.get()
    assert inquiry.name == "آرزو احمدی"
    assert inquiry.phone == "+989121112233"
    assert inquiry.consented_at is not None
    assert inquiry.ip_digest
    assert "." not in inquiry.ip_digest
    assert "127.0.0.1" not in inquiry.ip_digest


@pytest.mark.django_db
def test_public_contact_rejects_invalid_input_honeypot_and_rate_limit(client):
    url = reverse("website:contact")
    good = {
        "name": "بهاره نیکنام", "phone": "09121112233", "email": "",
        "topic": "guidance", "message": "اطلاعات بیشتری برای سالن می‌خواهم.",
        "consent": "on",
    }
    assert client.post(url, {**good, "message": "کوتاه"}).status_code == 200
    assert ContactInquiry.objects.count() == 0
    assert client.post(url, {**good, "website_url": "https://example.invalid"}).status_code == 200
    assert ContactInquiry.objects.count() == 0
    for i in range(5):
        assert client.post(url, {**good, "name": f"بهاره نیکنام {i}"}).status_code == 302
    limited = client.post(url, good)
    assert limited.status_code == 200
    assert ContactInquiry.objects.count() == 5
    assert "تعداد پیام‌های اخیر زیاد است" in limited.content.decode()


@pytest.mark.django_db
def test_contact_and_inquiry_status_are_csrf_and_superuser_protected(salon):
    client = Client(enforce_csrf_checks=True)
    url = reverse("website:contact")
    res = client.post(url, {
        "name": "مریم فلاح", "email": "maryam@example.com",
        "topic": "guidance", "message": "اطلاعات بیشتری درباره محصول می‌خواهم.",
        "consent": "on",
    })
    assert res.status_code == 403
    assert ContactInquiry.objects.count() == 0

    inquiry = ContactInquiry.objects.create(
        name="مریم فلاح", email="maryam@example.com",
        message="درخواست مشاوره درباره محصول", topic="guidance",
    )
    page = reverse("platform_admin:inquiries")
    assert client.get(page).status_code == 302
    staff = User.objects.create_user(phone="+989101041019", full_name="کارمند سالن")
    staff.is_staff = True
    staff.save(update_fields=["is_staff"])
    client.force_login(staff)
    assert client.get(page).status_code == 403

    operator = User.objects.create_superuser(
        phone="+989101041018", password="test-only-password",
    )
    client.force_login(operator)
    assert client.get(page).status_code == 200
    detail = reverse("platform_admin:inquiry_detail", kwargs={"inquiry_id": inquiry.pk})
    assert client.get(detail).status_code == 200
    assert client.post(detail, {"status": "closed", "internal_note": "بررسی و پاسخ ثبت شد"}).status_code == 403
    inquiry.refresh_from_db()
    assert inquiry.status == ContactInquiry.Status.NEW
