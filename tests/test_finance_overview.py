from datetime import datetime, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.utils.dates import jalali_month_bounds, jalali_three_previous_months_bounds
from apps.customers.models import Customer
from apps.finance.models import Payment, SalonDebt
from apps.finance.services import income_metrics
from apps.dashboard.role_services import day_bounds


@pytest.mark.django_db
def test_income_metrics_deposit_and_settle_on_different_days(client, owner_membership, salon):
    customer = Customer.objects.create(salon=salon, full_name="زهرا", phone="+989121111100")
    yesterday = timezone.localdate() - timedelta(days=1)
    today = timezone.localdate()
    tz = timezone.get_current_timezone()

    p1 = Payment.objects.create(
        salon=salon,
        customer=customer,
        paid_amount_toman=100_000,
        status=Payment.Status.PARTIAL,
    )
    p2 = Payment.objects.create(
        salon=salon,
        customer=customer,
        paid_amount_toman=400_000,
        status=Payment.Status.PAID,
    )
    Payment.objects.filter(pk=p1.pk).update(
        created_at=timezone.make_aware(datetime.combine(yesterday, datetime.min.time()), tz)
    )
    Payment.objects.filter(pk=p2.pk).update(
        created_at=timezone.make_aware(datetime.combine(today, datetime.min.time()), tz)
    )

    start, end = day_bounds(today)
    metrics = income_metrics(salon, start, end)
    assert metrics["total_received"] == 400_000
    assert metrics["settled_customer_count"] == 1
    assert metrics["deposit_customer_count"] == 0


@pytest.mark.django_db
def test_salon_debt_partial_payment(client, owner_membership, salon):
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()

    debt = SalonDebt.objects.create(
        salon=salon,
        creditor_name="تامین‌کننده",
        creditor_type=SalonDebt.CreditorType.BRAND,
        principal_toman=1_000_000,
    )
    url = reverse("finance:overview") + "?tab=debts"
    response = client.post(
        url,
        {"action": "pay_debt", "debt_id": debt.pk, "amount_toman": 400_000},
    )
    assert response.status_code == 302
    debt.refresh_from_db()
    assert debt.balance_toman == 600_000
    assert debt.is_closed is False

    client.post(url, {"action": "pay_debt", "debt_id": debt.pk, "amount_toman": 600_000})
    debt.refresh_from_db()
    assert debt.is_closed is True
    assert debt.balance_toman == 0


@pytest.mark.django_db
def test_jalali_month_bounds():
    start, end = jalali_month_bounds()
    assert start <= end


@pytest.mark.django_db
def test_jalali_three_months_bounds():
    start, end = jalali_three_previous_months_bounds()
    assert start <= end


@pytest.mark.django_db
def test_finance_tabs_have_one_header_and_clear_date_scope(client, owner_membership):
    client.force_login(owner_membership.user)
    url = reverse("finance:overview")
    for tab in ("income", "debts", "commissions"):
        response = client.get(url, {"tab": tab, "range": "month"})
        assert response.status_code == 200
        html = response.content.decode()
        assert html.count("<h1") == 1
        assert 'class="maison-unified-header ' not in html
        assert "css/luna-finance.css" in html
        assert ("finance-page__range-bar" in html) == (tab != "debts")
        if tab == "commissions":
            assert response.context["range_key"] == "day"


@pytest.mark.django_db
def test_invalid_debt_keeps_form_open_and_values(client, owner_membership, salon):
    client.force_login(owner_membership.user)
    response = client.post(reverse("finance:overview") + "?tab=debts", {
        "action": "add_debt", "creditor_name": "تست", "creditor_type": SalonDebt.CreditorType.PERSON,
        "principal_toman": "-1",
    })
    assert response.status_code == 200
    assert response.context["debt_form_open"]
    assert response.context["debt_form"].errors["principal_toman"]
    assert not SalonDebt.scoped(salon).exists()


@pytest.mark.django_db
def test_today_range_ignores_stale_day(client, owner_membership):
    client.force_login(owner_membership.user)
    response = client.get(reverse("finance:overview"), {"range": "today", "day": "2001-01-01"})
    assert response.status_code == 200
    assert response.context["selected_day"] == timezone.localdate()


@pytest.mark.django_db
def test_finance_dashboard_paginates_and_uses_real_scoped_trends(client, owner_membership, salon, salon_b):
    from django.contrib.staticfiles import finders

    today = timezone.localdate()
    start, _ = day_bounds(today)
    customer = Customer.objects.create(salon=salon, full_name="مشتری", phone="+989121233555")
    other = Customer.objects.create(salon=salon_b, full_name="خارج از سالن", phone="+989121233556")
    for index in range(6):
        payment = Payment.objects.create(salon=salon, customer=customer, paid_amount_toman=100_000, status=Payment.Status.PAID)
        Payment.objects.filter(pk=payment.pk).update(created_at=start + timedelta(minutes=index))
    previous = Payment.objects.create(salon=salon, customer=customer, paid_amount_toman=300_000, status=Payment.Status.PARTIAL)
    old_start, _ = day_bounds(today - timedelta(days=1))
    Payment.objects.filter(pk=previous.pk).update(created_at=old_start)
    hidden = Payment.objects.create(salon=salon_b, customer=other, paid_amount_toman=900_000, status=Payment.Status.PAID)
    Payment.objects.filter(pk=hidden.pk).update(created_at=start)
    client.force_login(owner_membership.user)
    response = client.get(reverse("finance:overview"))
    assert response.status_code == 200
    assert response.context["income"]["total_received"] == 600_000
    assert response.context["income"]["settled_customer_count"] == 1
    assert response.context["presentation"]["comparison"] == 100
    assert response.context["presentation"]["series"]["received"]
    assert response.context["payment_page"].paginator.count == 6
    assert len(response.context["payments"]) == 5
    assert "خارج از سالن" not in response.content.decode()
    assert "finance-hero-approved.webp" in response.content.decode()
    assert finders.find("images/photos/beautyos-finance-hero.webp")
    response = client.get(reverse("finance:overview"), {"page": 2})
    assert len(response.context["payments"]) == 1
    response = client.get(reverse("finance:overview"), {"rows": 50})
    assert len(response.context["payments"]) == 6


@pytest.mark.django_db
def test_finance_empty_does_not_invent_change_or_sparklines(client, owner_membership):
    client.force_login(owner_membership.user)
    response = client.get(reverse("finance:overview"))
    assert response.status_code == 200
    assert response.context["presentation"]["comparison"] is None
    assert not any(response.context["presentation"]["series"].values())
    assert response.context["payment_page"].paginator.count == 0


@pytest.mark.django_db
def test_finance_premium_hero_uses_local_art_and_preserves_all_financial_tabs(client, owner_membership):
    from pathlib import Path
    from django.contrib.staticfiles import finders

    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(owner_membership.salon_id)
    session.save()
    for tab in ("income", "cash", "commissions", "debts", "reports"):
        response = client.get(reverse("finance:overview"), {"tab": tab})
        assert response.status_code == 200
        html = response.content.decode()
        assert html.count("<h1") == 1
        assert "finance-page__header--premium" in html
        assert "finance-hero-approved.webp" in html
        assert "finance-premium-header.css" in html
        assert "beautyos-finance-hero.webp" not in html
        assert "درآمد، هزینه‌ها، تسویه متخصصان و سود سالن" in html
        assert 'class="finance-page__tabs finance-phase2-tabs"' in html
        assert ("finance-page--dashboard" in html) == (tab == "income")
        if tab != "debts":
            assert 'finance-page__range-bar' in html

    art_path = finders.find("images/finance-hero-approved.webp")
    style_path = finders.find("css/finance-premium-header.css")
    assert art_path is not None and style_path is not None
    art_content = Path(art_path).read_bytes()
    assert art_content[:4] == b"RIFF" and art_content[8:12] == b"WEBP"
    styles = Path(style_path).read_text(encoding="utf-8")
    assert "finance-page--dashboard" in styles
    assert "@media(max-width:720px)" in styles
    assert "overflow:visible" in styles


@pytest.mark.django_db
def test_finance_quick_actions_and_balances_compact_layout(client, owner_membership):
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(owner_membership.salon_id)
    session.save()
    for tab in ("income", "cash"):
        response = client.get(reverse("finance:overview"), {"tab": tab})
        assert response.status_code == 200
        html = response.content.decode()
        assert 'class="fin-panel fin-quick-actions-panel"' not in html
        assert ("fin-balances-panel" in html) == (tab == "income")
        assert ("fin-quick-grid--compact" in html) == (tab == "income")


@pytest.mark.django_db
def test_finance_insights_keep_values_but_collapses_explanatory_text(client, owner_membership):
    """Insights use a compact presentation without hiding financial figures or source notes."""
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(owner_membership.salon_id)
    session.save()
    response = client.get(reverse("finance:overview"), {"tab": "income"})
    assert response.status_code == 200
    html = response.content.decode()
    assert "fin-insights-grid--minimal" in html
    assert "fin-insight-panel--trend" in html
    assert "fin-insight-panel--mix" in html
    assert "fin-method-ring" in html
    assert "fin-method-list" in html
    assert "درباره نمودار" in html
    assert "توضیح محاسبه" in html
    assert html.count('class="fin-insight-caveat"') == 2
    assert "خالص دریافتی" in html

    cash = client.get(reverse("finance:overview"), {"tab": "cash"})
    assert cash.status_code == 200
    cash_html = cash.content.decode()
    assert "fin-insights-grid--minimal" not in cash_html
    assert "fin-insight-panel--mix" not in cash_html
    assert "ترکیب دریافتی‌ها" not in cash_html
    assert "fin-quick-grid--compact" not in cash_html


@pytest.mark.django_db
def test_finance_commissions_only_in_quick_actions_not_top_tabs(client, owner_membership):
    """Remove duplicate top navigation item, preserving the working quick action and route."""
    from django.urls import reverse

    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(owner_membership.salon_id)
    session.save()
    for tab in ("income", "cash", "commissions"):
        response = client.get(reverse("finance:overview"), {"tab": tab})
        assert response.status_code == 200
        html = response.content.decode()
        top_nav = html.split('<nav class="finance-page__tabs finance-phase2-tabs"', 1)[1].split("</nav>", 1)[0]
        assert "?tab=commissions" not in top_nav
        assert "تسویه متخصصان</span>" not in top_nav
        if tab == "income" and response.context.get("can_settle_commission"):
            assert "?tab=commissions" in html
    commissions = client.get(reverse("finance:overview"), {"tab": "commissions"})
    assert commissions.status_code == 200
    assert 'aria-label="تسویه متخصص‌ها"' in commissions.content.decode()

@pytest.mark.django_db
def test_commission_destination_hierarchy_and_accessible_panels(client, owner_membership):
    """Specialist settlement comes before salary tools, with back navigation and accessible controls."""
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(owner_membership.salon_id)
    session.save()

    response = client.get(reverse("finance:overview"), {"tab": "commissions"})
    assert response.status_code == 200
    html = response.content.decode()
    assert html.count('aria-label="تسویه متخصص‌ها"') == 1
    assert html.index('aria-label="تسویه متخصص‌ها"') < html.index("مدل همکاری و حقوق")
    assert 'class="finance-comm-back"' in html
    for panel in ("pending", "settled"):
        assert f'aria-controls="finance-comm-{panel}-panel"' in html
        assert f'id="finance-comm-{panel}-panel"' in html
    assert "تسویه متخصصان</h2>" in html


@pytest.mark.django_db
def test_commission_workspace_search_and_calendar(client, owner_membership):
    client.force_login(owner_membership.user)
    response = client.get(reverse("finance:overview"), {"tab": "commissions", "q": "نام آزمایشی"})
    assert response.status_code == 200
    assert response.context["commission_query"] == "نام آزمایشی"
    html = response.content.decode()
    assert "finance-page--commissions" in html
    assert 'id="commission-search"' in html
    assert "finance-comm-date" in html
    assert "finance-comm-cooperation" in html
    assert "نام آزمایشی" in html


@pytest.mark.django_db
def test_cash_dashboard_compact_cards_and_customer_search(client, owner_membership, salon):
    client.force_login(owner_membership.user)
    customer = Customer.objects.create(salon=salon, full_name="مریم خاص", phone="+989121334455")
    Payment.objects.create(salon=salon, customer=customer, paid_amount_toman=500000, status=Payment.Status.PAID)
    response = client.get(reverse("finance:overview"), {"tab": "cash", "q": "مریم"})
    assert response.status_code == 200
    assert response.context["cash_paid_total"] == 500000
    assert response.context["payment_page"].paginator.count == 1
    assert "finance-cash-kpis" in response.content.decode()
    assert "finance-cash-tools" in response.content.decode()
    assert "fin-balances-panel" not in response.content.decode()
    empty = client.get(reverse("finance:overview"), {"tab": "cash", "q": "نام ناموجود"})
    assert empty.context["payment_page"].paginator.count == 0
    assert empty.context["cash_paid_total"] == 500000


@pytest.mark.django_db
def test_cash_filter_has_only_today_and_calendar(client, owner_membership):
    client.force_login(owner_membership.user)
    response = client.get(reverse("finance:overview"), {"tab": "cash", "q": "مریم"})
    assert response.status_code == 200
    html = response.content.decode().split('class="finance-page__range-bar finance-comm-filter finance-cash-filter"', 1)[1].split("</section>", 1)[0]
    assert 'id="cash-search"' in html
    assert 'staff-board-search__submit' in html
    assert 'finance-page__day-picker' in html
    assert 'range=today' in html
    assert 'value="مریم"' in html
    for other in ("range=yesterday", "range=week", "range=month", "range=quarter", "انتخاب روز"):
        assert other not in html
    legacy = client.get(reverse("finance:overview"), {"tab": "cash", "range": "month"})
    assert legacy.context["range_key"] == "day"


@pytest.mark.django_db
def test_receipts_search_stable_invoice_number(client, owner_membership, salon):
    from uuid import uuid4
    from apps.finance.models import Invoice
    client.force_login(owner_membership.user)
    customer = Customer.objects.create(salon=salon, full_name="مشتری فاکتور", phone="+989121212390")
    invoice = Invoice.objects.create(salon=salon, customer=customer, customer_name=customer.full_name, request_key=uuid4(), request_digest="x", gross_toman=800000)
    assert invoice.invoice_number == f"BF-{invoice.pk:06d}"
    for query in (invoice.invoice_number, "مشتری فاکتور"):
        response = client.get(reverse("finance:overview"), {"tab": "receipts", "q": query})
        assert response.status_code == 200
        assert list(response.context["invoice_page"]) == [invoice]
        assert invoice.invoice_number in response.content.decode()
        assert 'id="invoice-search"' in response.content.decode()
