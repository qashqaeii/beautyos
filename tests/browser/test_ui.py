"""Real Chromium smoke tests against Django, with actual Persian fonts and JS.
Run only against the isolated test database; no external runtime requests allowed.
"""
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

pw = pytest.importorskip("playwright.sync_api")

ARTIFACT = Path("browser-artifacts")


@pytest.fixture
def browser_data(owner_membership):
    from apps.appointments.models import Appointment
    from apps.commissions.models import CommissionEntry, CommissionRule
    from apps.customers.models import Customer
    from apps.expenses.models import Expense
    from apps.inventory.models import InventoryItem
    from apps.loyalty.models import LoyaltyAccount
    from apps.packages.models import ServicePackage, CustomerPackage
    from apps.services.models import Service
    from apps.staff.models import StaffProfile, StaffWorkHours
    from datetime import time

    salon = owner_membership.salon
    staff, _ = StaffProfile.objects.get_or_create(
        salon=salon, membership=owner_membership,
        defaults={"display_name": "متخصص تست", "title": "آرایش و مراقبت"},
    )
    service = Service.objects.create(salon=salon, name="کوتاهی و حالت‌دهی مو", price_toman=1250000)
    staff.services.add(service)
    for weekday in range(7):
        StaffWorkHours.objects.get_or_create(salon=salon, staff=staff, weekday=weekday,
            defaults={"start_time":time(9), "end_time":time(18)})
    customer = Customer.objects.create(salon=salon, full_name="مشتری آزمایشی با نام نسبتاً طولانی", phone="+989121234999")
    start = timezone.now() + timedelta(hours=2)
    appt = Appointment.objects.create(salon=salon, customer=customer, staff=staff, service=service,
        start_at=start, end_at=start+timedelta(minutes=30), price_toman=1250000,
        status=Appointment.Status.CONFIRMED)
    Expense.objects.create(salon=salon, amount_toman=350000, expense_date=timezone.localdate(), description="مواد مصرفی")
    InventoryItem.objects.create(salon=salon,name="شامپو تخصصی",quantity=4,minimum_quantity=5)
    CommissionRule.objects.create(salon=salon, name="سهم متخصص", percent=30)
    CommissionEntry.objects.create(salon=salon,staff=staff,base_amount_toman=1250000,commission_amount_toman=375000)
    pack=ServicePackage.objects.create(salon=salon,name="پکیج مراقبت مو",price_toman=4000000,session_count=4)
    CustomerPackage.objects.create(salon=salon,customer=customer,package=pack,sessions_total=4,
        expires_at=timezone.now()+timedelta(days=30),price_paid_toman=4000000)
    account,_=LoyaltyAccount.objects.get_or_create(salon=salon,customer=customer,defaults={"points_balance":250})
    return salon, staff, customer, appt, account


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("width,height", [(360,800),(768,1024),(1280,720),(1440,900)])
def test_real_browser_layout_and_controls(live_server, client, owner_membership, browser_data, width, height):
    salon, staff, customer, appt, account = browser_data
    from apps.appointments.models import Appointment
    from apps.finance.models import Invoice, Payment, ProductSale, Refund
    from apps.loyalty.models import LoyaltyVoucher
    voucher=LoyaltyVoucher.objects.create(salon=salon,customer=customer,title="اعتبار تست",amount_toman=50000,expires_on=timezone.localdate())
    from apps.inventory.models import InventoryItem
    item=InventoryItem.scoped(salon).get(name="شامپو تخصصی")
    item.purchase_price_toman=150000
    item.save(update_fields=["purchase_price_toman"])

    prior = timezone.now() - timedelta(hours=2)
    completed = Appointment.objects.create(salon=salon, customer=customer, staff=staff, service=appt.service,
        start_at=prior, end_at=prior+timedelta(minutes=30), completed_at=prior+timedelta(minutes=30),
        price_toman=1250000,status=Appointment.Status.COMPLETED)
    ARTIFACT.mkdir(exist_ok=True)
    client.force_login(owner_membership.user)
    session=client.session
    session["active_salon_id"]=str(salon.pk)
    session.save()
    cookie=client.cookies[settings.SESSION_COOKIE_NAME].value
    public_pages = [
        ("home","/"),("login","/auth/login/"),("register","/auth/register/"),
        ("features","/features/"),("faq","/faq/"),
        ("storefront",reverse("salons_public:landing",kwargs={"slug":salon.slug})),
        ("booking",reverse("salons_public:booking_start",kwargs={"slug":salon.slug})),
    ]
    workspace_pages=[
        ("overview","/app/"),("management","/app/management/"),("reception","/reception/"),
        ("calendar","/appointments/"),("specialists","/app/specialists/"),
        ("customers","/customers/"),("customer-detail",reverse("customers:detail",args=[customer.pk])),
        ("staff","/staff/"),("staff-detail",reverse("staff:detail",args=[staff.pk])),
        ("staff-hours",reverse("staff:hours",args=[staff.pk])),("services","/services/"),
        ("finance","/finance/"),("finance-commissions","/finance/?tab=commissions"),("finance-debts","/finance/?tab=debts"),("finance-cash","/finance/?tab=cash"),("finance-reports","/finance/?tab=reports"),("finance-receipts","/finance/?tab=receipts"),
        ("finance-checkout-customers",reverse("finance:checkout_customers")),
        ("finance-checkout",reverse("finance:checkout",args=[customer.pk])),
        ("finance-invoices",reverse("finance:invoices")),
        ("finance-cash-close",reverse("finance:cash_close")),
        ("finance-accounts",reverse("finance:accounts")),
        ("finance-staff",reverse("finance:staff_finance")),
        ("finance-recurring",reverse("finance:recurring")),
        ("finance-product-sales",reverse("finance:product_sales")),
        ("finance-materials",reverse("finance:materials")),
        ("expenses","/expenses/"),("commissions","/commissions/"),
        ("commission-rules","/commissions/rules/"),("packages","/packages/"),
        ("inventory","/inventory/"),("loyalty","/loyalty/"),
        ("loyalty-detail",reverse("loyalty:member",args=[account.pk])),
        ("loyalty-program",reverse("loyalty:program")),
        ("loyalty-rewards",reverse("loyalty:rewards")),
        ("loyalty-birthdays",reverse("loyalty:birthdays")),
        ("loyalty-referrals",reverse("loyalty:referrals")),
        ("loyalty-vouchers",reverse("loyalty:vouchers")),
        ("loyalty-memberships",reverse("loyalty:memberships")),
        ("loyalty-insights",reverse("loyalty:insights")),
        ("retention","/retention/"),("marketing-campaigns",reverse("retention:campaigns")),("marketing-automation",reverse("retention:automation")),("waitlist","/waitlist/"),
        ("portfolio","/portfolio/"),("members","/members/"),("settings","/settings/"),
        ("appointment-detail",reverse("appointments:detail",args=[appt.pk])),
    ]
    errors=[]
    with pw.sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True)
        context=browser.new_context(viewport={"width":width,"height":height},locale="fa-IR",reduced_motion="reduce")
        page=context.new_page()
        external=[]
        js_errors=[]
        broken=[]
        origin=urlsplit(live_server.url).netloc
        def route_local(route):
            target=urlsplit(route.request.url)
            if target.scheme in ("http","https") and target.netloc!=origin:
                external.append(route.request.url)
                route.abort()
            else:
                route.continue_()
        context.route("**/*",route_local)
        page.on("pageerror",lambda error:js_errors.append(str(error)))
        page.on("response",lambda response:broken.append(f"{response.status}: {response.url}") if response.status>=400 and response.request.resource_type in ("script","stylesheet","font","image") else None)
        def visit(name,path,workspace=False):
            external.clear(); js_errors.clear(); broken.clear()
            try:
                response=page.goto(live_server.url+path,wait_until="load",timeout=20000)
                assert response is not None and response.status==200, f"HTTP {response.status if response else 'none'}"
                assert urlsplit(page.url).path==urlsplit(path).path, f"unexpected redirect {page.url}"
                page.wait_for_function("window.Alpine && window.htmx && window.lucide",timeout=10000)
                page.evaluate("document.fonts.ready")
                assert page.evaluate("document.documentElement.dir")== "rtl"
                if workspace:
                    assert page.locator("#workspace-content").is_visible()
                    assert page.locator("h1:visible").count()==1, "missing/duplicate page heading"
                    assert page.evaluate("getComputedStyle(document.querySelector('.maison-main')).overflowY === 'visible'"), "nested workspace scroll"
                    if width >= 1024:
                        pw.expect(page.locator(".luna-active-salon")).to_have_text(salon.name)
                        assert page.locator(".maison-sidebar .luna-salon-switch-list").count() == 0
                        assert page.evaluate("getComputedStyle(document.querySelector('#workspace-sidebar-nav')).overflowY === 'auto'"), "desktop sidebar should scroll its own navigation"
                        assert page.evaluate("getComputedStyle(document.querySelector('.maison-sidebar--premium')).position === 'sticky'"), "desktop sidebar must remain sticky"
                        if name == "reception":
                            before = page.locator(".maison-sidebar--premium").bounding_box()
                            max_scroll = page.evaluate("document.documentElement.scrollHeight - innerHeight")
                            page.evaluate("window.scrollTo(0, 450)")
                            page.wait_for_timeout(100)
                            after = page.locator(".maison-sidebar--premium").bounding_box()
                            assert before and after and abs(before["y"] - after["y"]) < 3, "desktop sidebar moved while reception content scrolled"
                            if max_scroll > 3:
                                assert page.evaluate("window.scrollY > 0"), "long reception pages must remain scrollable"
                            else:
                                assert page.evaluate("window.scrollY === 0"), "compact reception should fit without page scroll"
                            page.evaluate("window.scrollTo(0, 0)")
                if workspace and width >= 1024:
                    standardized_headers = {
                        "customers": ".customers-list-page__header",
                        "staff": ".staff-team-page__header",
                        "finance": ".finance-page__header--premium",
                        "reception": ".reception-desk-header",
                    }
                    header_selector = standardized_headers.get(name)
                    if header_selector:
                        header = page.locator(header_selector).first
                        pw.expect(header).to_be_visible()
                        header_height = header.evaluate("(el) => el.getBoundingClientRect().height")
                        assert abs(header_height - 88) <= 3, f"{name} page header height differs: {header_height}px"
                        # Decorative art/pseudo-elements can enlarge scrollHeight even
                        # when clipped correctly. Validate the visible heading geometry.
                        title = header.locator("h1").first
                        pw.expect(title).to_be_visible()
                        head_box, title_box = header.bounding_box(), title.bounding_box()
                        assert head_box and title_box
                        assert title_box["y"] >= head_box["y"] - 3
                        assert title_box["y"] + title_box["height"] <= head_box["y"] + head_box["height"] + 3, (
                            f"{name} visible header title is clipped"
                        )
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2"), "horizontal page overflow"
                assert page.locator('link[href*="phase7-ui-polish.css"]').count() == 1, "phase 7 styling missing"
                if width <= 639 and name == "reception":
                    invoice_inputs = page.locator(".reception-flow__invoice-fields input")
                    if invoice_inputs.count():
                        assert invoice_inputs.first.evaluate(
                            "(el) => el.getBoundingClientRect().width <= el.parentElement.getBoundingClientRect().width + 2"
                        ), "reception invoice amount extends outside its field"
                    actions = page.locator(".reception-flow__invoice-controls > button")
                    if actions.count():
                        assert actions.first.evaluate(
                            "(el) => el.getBoundingClientRect().height >= 42"
                        ), "reception invoice actions are too small to tap"

                assert not external, f"external runtime requests {external}"
                assert not broken, f"broken static assets {broken}"
                assert not js_errors, f"JavaScript exceptions {js_errors}"
                if name in {"finance", "finance-commissions"}:
                    tabs = page.locator(".finance-page__tabs.finance-phase2-tabs .finance-page__tab")
                    assert tabs.count() == 7, "finance tabs mismatch after moving settlement to quick actions"
                    row_counts = tabs.evaluate_all("""(nodes) => {
                        const rows = [];
                        for (const node of nodes) {
                            const top = node.getBoundingClientRect().top;
                            const last = rows[rows.length - 1];
                            if (last && Math.abs(last.top - top) < 3) last.count++;
                            else rows.push({top, count: 1});
                        }
                        return rows.map(row => row.count);
                    }""")
                    assert row_counts == ([7] if width >= 1100 else [4, 3]), f"unbalanced finance tabs: {row_counts}"
                if name == "finance-commissions":
                    pw.expect(page.locator(".finance-comm-heading")).to_be_visible()
                    pw.expect(page.locator(".finance-comm-back")).to_be_visible()
                    page.locator('[aria-controls="finance-comm-settled-panel"]').click()
                    pw.expect(page.locator("#finance-comm-settled-panel")).to_be_visible()
                    pw.expect(page.locator("#finance-comm-pending-panel")).not_to_be_visible()
                    page.locator('[aria-controls="finance-comm-pending-panel"]').click()
                    pw.expect(page.locator("#finance-comm-pending-panel")).to_be_visible()
                if name == "finance":
                    header = page.locator(".finance-page__header--premium")
                    pw.expect(header).to_be_visible()
                    pw.expect(header.get_by_role("heading", name="مدیریت مالی")).to_be_visible()
                    art = header.locator(".luna-finance-hero-art img")
                    assert art.evaluate("(img) => img.complete && img.naturalWidth > 0"), "approved finance illustration missing"
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 3"), "finance horizontal viewport overflow"
                    actions = page.locator(".fin-quick-actions-panel")
                    balances = page.locator(".fin-balances-panel")
                    pw.expect(actions).to_be_visible()
                    pw.expect(balances).to_be_visible()
                    pw.expect(balances.locator(".fin-balance-item")).to_have_count(8)
                    action_box = actions.bounding_box()
                    balances_box = balances.bounding_box()
                    assert action_box and balances_box
                    assert action_box["y"] + action_box["height"] <= balances_box["y"] + 3, "finance quick actions should be a separate compact strip"
                    assert action_box["height"] < (148 if width >= 1024 else 270), "unnecessary empty space inside finance quick actions"
                    assert page.evaluate("getComputedStyle(document.querySelector('.fin-quick-grid--compact')).gridTemplateColumns.split(' ').length === 1"), "finance balance layout must be stacked"
                    insight_panels = page.locator(".fin-insights-grid--minimal > .fin-panel")
                    pw.expect(insight_panels).to_have_count(2)
                    assert page.evaluate("() => { const panels = [...document.querySelectorAll('.fin-insights-grid--minimal > .fin-panel')]; return panels.every((el) => el.scrollHeight <= el.clientHeight + 2); }"), "finance insight content clipped"
                    assert page.locator(".fin-insight-panel--mix .fin-method-ring").is_visible()
                    if width >= 1024:
                        # The CSS deliberately stretches both insight cards to the height
                        # of the taller one. Chromium measured 210.09375px, so checking
                        # < 210px was a fractional-pixel false positive, not a clipped chart.
                        trend_box = insight_panels.nth(0).bounding_box()
                        mix_box = insight_panels.nth(1).bounding_box()
                        assert trend_box and mix_box
                        assert trend_box["height"] <= mix_box["height"] + 3, "finance trend has excess height beyond its peer"
                        assert trend_box["height"] < 240, "finance trend occupies excessive vertical space"
                        assert mix_box["height"] < 270, "finance income breakdown too tall"
                    caveat = page.locator(".fin-insight-panel--mix .fin-insight-caveat")
                    pw.expect(caveat).to_be_visible()
                    caveat.locator("summary").click()
                    assert caveat.evaluate("(el) => el.open"), "finance explanatory note must stay accessible"
                if name == "customer-detail":
                    assert page.locator(".customer-detail-header__avatar--icon").count() == 1
                    assert page.locator(".customer-detail-hero-art__glass svg").count() == 1
                    assert page.locator(".customer-detail-hero-art").evaluate(
                        "(el) => getComputedStyle(el).display === 'none'"
                    ), "customer hero must use the same restrained icon treatment as other management pages"
                    assert page.locator(".customer-detail-header").evaluate(
                        "(el) => getComputedStyle(el).backgroundImage.includes('linear-gradient')"
                    )
                    assert page.locator(".customer-detail-card--main").evaluate(
                        "(el) => getComputedStyle(el).color === 'rgb(80, 62, 55)'"
                    ), "appointments must inherit the shared management ink color"

                    assert page.locator(".customer-detail-hero-title h1").inner_text() == "پروفایل مشتری"
                    assert page.locator(".customer-detail-header__content").is_visible()
                    header_title = page.locator(".customer-detail-hero-title").bounding_box()
                    identity = page.locator(".customer-detail-header__content").bounding_box()
                    assert header_title and identity
                    assert header_title["y"] + header_title["height"] <= identity["y"] - 2, (
                        "customer profile title must not overlap the identity card"
                    )


                    assert page.locator(".customer-detail-header img.customer-detail-header__avatar").count() == 0
                    upcoming = page.locator(".customer-detail-workspace__primary > .customer-detail-card--main")
                    pw.expect(upcoming).to_be_visible()
                    assert page.locator(".customer-detail-workspace__aside .customer-detail-card--notes").count() == 1
                    assert page.locator(".customer-detail-workspace__aside .customer-detail-card--preferences").count() == 1
                    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 3")
                    main_box = upcoming.bounding_box()
                    aside_box = page.locator(".customer-detail-workspace__aside").bounding_box()
                    assert main_box and aside_box
                    if width >= 900:
                        assert abs(main_box["y"] - aside_box["y"]) < 8, "customer sections should share a row"
                        assert main_box["width"] > aside_box["width"], "upcoming appointments must be the primary column"
                        if width >= 1180 and height >= 560:
                            profile = page.locator(".customer-detail-page").bounding_box()
                            assert profile and profile["y"] + profile["height"] <= height + 3, "customer profile must fit desktop viewport"
                            cards = page.locator(".customer-detail-history > .customer-detail-card")
                            assert cards.count() >= 1
                            for card in cards.all():
                                box = card.bounding_box()
                                assert box and box["y"] + box["height"] <= height + 3, "history card extends beyond desktop viewport"

                    else:
                        assert aside_box["y"] >= main_box["y"] + main_box["height"] - 4, "mobile customer cards should stack below upcoming appointments"
                if name == "staff-detail":
                    book_link = page.locator('.staff-profile-header__actions a[href*="book=1"]').first
                    if book_link.count():
                        book_link.click()
                        modal = page.locator(".appointment-booking-modal")
                        pw.expect(modal).to_be_visible()
                        pair = modal.locator(".appt-booking-modal__primary-pair > .appt-booking-section--modal")
                        pw.expect(pair).to_have_count(2)
                        box_a = pair.nth(0).bounding_box()
                        box_b = pair.nth(1).bounding_box()
                        assert box_a and box_b
                        if width >= 640:
                            assert abs(box_a["y"] - box_b["y"]) <= 3, "customer and service cards must share a row"
                        else:
                            assert box_b["y"] >= box_a["y"] + box_a["height"] - 2, "mobile cards must stack"
                        dates = modal.locator(".appt-booking-datetime > .customer-form-field")
                        pw.expect(dates).to_have_count(2)
                        modal.locator(".appt-booking-advanced__toggle").click()
                        pw.expect(modal.locator(".appt-booking-status-card")).to_be_visible()
                        if modal.locator(".appt-booking-deposit--modal").count():
                            deposit = modal.locator(".appt-booking-deposit--modal").bounding_box()
                            status = modal.locator(".appt-booking-status-card").bounding_box()
                            assert deposit and status
                            if width >= 640:
                                assert abs(deposit["y"] - status["y"]) <= 3, "deposit and status must share a row"
                        footer = modal.locator(".inventory-create-modal__foot")
                        current_box = modal.bounding_box()
                        footer_box = footer.bounding_box()
                        assert current_box and footer_box
                        assert footer_box["y"] + footer_box["height"] <= current_box["y"] + current_box["height"] + 3, "booking actions must stay inside the modal"
                        modal.locator(".inventory-create-modal__close").click()
                        pw.expect(modal).not_to_be_visible()
                if name == "reception":
                    kpis = page.locator(".reception-overview-kpis > .reception-overview-kpi")
                    pw.expect(kpis).to_have_count(4)
                    header = page.locator(".reception-desk-header").bounding_box()
                    kpi_box = page.locator(".reception-overview-kpis").bounding_box()
                    assert header and kpi_box and kpi_box["y"] >= header["y"] + header["height"] - 2
                    buttons = page.locator(".reception-overview-actions")
                    if buttons.count():
                        action_box = buttons.bounding_box()
                        assert action_box and action_box["y"] >= kpi_box["y"] + kpi_box["height"] - 2
                    assert page.locator('link[href*="reception-dashboard-v3.css"]').count() == 1
                    flow = page.locator(".reception-flow")
                    pw.expect(flow).to_be_visible()
                    if width >= 1180 and height >= 650:
                        layout = page.locator(".reception-desk-layout").bounding_box()
                        flow_box = flow.bounding_box()
                        next_box = page.locator(".reception-desk-priority").bounding_box()
                        team_box = page.locator(".reception-desk-workspace__team").bounding_box()
                        assert layout and flow_box and next_box and team_box
                        assert flow_box["width"] > next_box["width"], "today operations must be the main panel"
                        assert abs(flow_box["y"] - next_box["y"]) <= 3, "today and next appointment must share a row"
                        assert team_box["y"] >= flow_box["y"] + flow_box["height"] - 2, "team and free slots belong below operations"
                        assert page.locator(".reception-desk-page").evaluate(
                            "(el) => el.getBoundingClientRect().bottom <= innerHeight + 3"
                        ), "reception desk must fit the standard desktop viewport"
                if name == "customers":
                    # Directory must never nest a vertical scroller or clip customer cards.
                    assert page.evaluate("getComputedStyle(document.querySelector('.maison-main')).overflowY === 'visible'"), "nested workspace scroll"
                    assert page.evaluate("getComputedStyle(document.querySelector('.customers-list-grid')).overflowY === 'visible'"), "customer cards should not be clipped"
                    if page.locator(".customers-list-page__pagination").count():
                        assert page.evaluate("() => { const cards = document.querySelectorAll('.customers-list-card'); const pager = document.querySelector('.customers-list-page__pagination'); return !cards.length || pager.getBoundingClientRect().top >= cards[cards.length-1].getBoundingClientRect().bottom - 2; }"), "pagination overlaps last customer row"
                    hero = page.locator(".customers-list-page__header")
                    art = hero.locator(".customers-hero__art img")
                    pw.expect(art).to_be_visible()
                    assert art.evaluate("(img) => img.complete && img.naturalWidth > 0"), "customer hero illustration not loaded"
                    assert hero.evaluate("(el) => getComputedStyle(el, '::before').display === 'none'"), "shared flower hero still visible"
                    pw.expect(hero.locator(".customers-list-page__add")).to_be_visible()
                if name in {"home","login","overview","management","reception","calendar","customers","customer-detail","staff-detail","services","finance","packages","inventory","loyalty","storefront"}:
                    page.screenshot(path=str(ARTIFACT/f"{width}-{name}.png"),animations="disabled")
            except Exception as exc:
                errors.append(f"{width}/{name}: {exc}")
                try:
                    page.screenshot(path=str(ARTIFACT/f"FAIL-{width}-{name}.png"),animations="disabled",timeout=4000)
                except Exception:
                    pass
        for name,path in public_pages:
            visit(name,path)
        context.add_cookies([{"name":settings.SESSION_COOKIE_NAME,"value":cookie,"url":live_server.url}])
        for name,path in workspace_pages:
            visit(name,path,True)

        if width>=1024:
            try:
                # Typical 1366x768 laptop with browser chrome leaves roughly 640 CSS px.
                page.set_viewport_size({"width":1366,"height":640})
                page.goto(live_server.url+"/app/",wait_until="load")
                page.evaluate("document.fonts.ready")
                page.evaluate("window.scrollTo(0,0)")
                for selector in (".overview-kpis",".overview-revenue",".overview-status"):
                    pw.expect(page.locator(selector)).to_be_in_viewport(ratio=1)
                for selector in ("#overview-staff-title","#overview-customer-title"):
                    pw.expect(page.locator(selector)).to_be_in_viewport(ratio=1)
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth+2")
                assert page.evaluate("window.scrollY")==0
                page.screenshot(path=str(ARTIFACT/"1366-overview-compact.png"),animations="disabled")
                page.goto(live_server.url+reverse("loyalty:overview"),wait_until="load")
                page.evaluate("document.fonts.ready")
                page.evaluate("window.scrollTo(0,0)")
                header=page.locator(".loyalty-members-table__head")
                pw.expect(header).to_be_in_viewport(ratio=1)
                first=page.locator(".loyalty-members-table__row--body").first
                pw.expect(first).to_be_in_viewport(ratio=.25)
                assert page.evaluate("window.scrollY")==0
                page.screenshot(path=str(ARTIFACT/"1366-loyalty-compact.png"),animations="disabled")
                page.goto(live_server.url + "/reception/", wait_until="load")
                page.evaluate("document.fonts.ready")
                page.evaluate("window.scrollTo(0,0)")
                reception_page = page.locator(".reception-desk-page")
                pw.expect(reception_page).to_be_visible()
                assert reception_page.evaluate(
                    "(el) => el.getBoundingClientRect().bottom <= innerHeight + 3"
                ), "reception should fit the 1366x640 laptop content viewport"
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 3")
                assert page.evaluate("document.documentElement.scrollHeight <= innerHeight + 3")
                page.screenshot(path=str(ARTIFACT/"1366-reception-compact.png"),animations="disabled")

            except Exception as exc:
                errors.append(f"1366/overview, loyalty or reception first viewport: {exc}")
            finally:
                page.set_viewport_size({"width":width,"height":height})

        def modal(path,trigger,name):
            try:
                page.goto(live_server.url+path,wait_until="load")
                page.locator(trigger).click(timeout=10000)
                dialog=page.get_by_role("dialog",name=name,exact=True)
                pw.expect(dialog).to_be_visible(timeout=6000)
                box=dialog.bounding_box()
                assert box and box["x"]>=-2 and box["x"]+box["width"]<=width+2
                assert box["height"] <= height * (0.92 if width < 640 else 0.84) + 2
                if width >= 640:
                    limit = dialog.evaluate("(el) => el.classList.contains('luna-modal--extended') ? 620 : el.classList.contains('luna-modal--compact') ? 420 : 520")
                    assert box["width"] <= limit + 2, "oversized desktop dialog"
                    assert box["height"] <= 562, "oversized desktop dialog height"
                assert dialog.evaluate("(el) => el.scrollWidth <= el.clientWidth + 2"), "modal content has horizontal overflow"
                if name == "مشتری جدید":
                    advanced = dialog.locator(".customer-form-advanced__toggle")
                    advanced.click()
                    cards = dialog.locator(".luna-modal-choice-grid > .customer-form-field--checkbox")
                    pw.expect(cards).to_have_count(2)
                    pw.expect(cards.nth(0)).to_be_visible()
                    pw.expect(cards.nth(1)).to_be_visible()
                    first_box, second_box = cards.nth(0).bounding_box(), cards.nth(1).bounding_box()
                    assert first_box and second_box
                    assert abs(first_box["y"] - second_box["y"]) <= 3, "VIP and marketing choices must share a row"
                    assert first_box["x"] + first_box["width"] <= second_box["x"] + 3 or second_box["x"] + second_box["width"] <= first_box["x"] + 3, "choice cards must not overlap"
                footer = dialog.locator(".inventory-create-modal__foot")
                pw.expect(footer).to_be_visible()
                # Expanding optional fields changes the dialog's geometry.
                # Compare both rectangles AFTER the expansion, not to its old bounding box.
                current_box = dialog.bounding_box()
                footer_box = footer.bounding_box()
                assert current_box and footer_box and footer_box["y"] + footer_box["height"] <= current_box["y"] + current_box["height"] + 2
                assert dialog.evaluate("(el) => getComputedStyle(el, '::before').content === 'none' || getComputedStyle(el, '::before').display === 'none'"), "decorative modal panel still present"
                page.screenshot(path=str(ARTIFACT/f"{width}-modal-{name}.png"),animations="disabled")
                page.keyboard.press("Escape")
                pw.expect(dialog).not_to_be_visible(timeout=6000)
            except Exception as exc:
                errors.append(f"{width}/{name} interaction: {exc}")
        modal("/customers/",".customers-list-page__add","مشتری جدید")
        modal("/staff/",".staff-team-page__add","افزودن متخصص")
        modal(reverse("staff:detail",args=[staff.pk]),"button.staff-profile-header__btn:has-text('ویرایش')","ویرایش پروفایل")
        # Native loyalty dialogs keep forms in the parent view and return focus on Escape.
        for route,dialog_id in [("overview","club-adjust"),("overview","club-program"),("rewards","club-reward"),("rewards","club-redeem"),("referrals","club-referral"),("vouchers","club-voucher"),("memberships","club-membership")]:
            try:
                page.goto(live_server.url+reverse("loyalty:"+route),wait_until="load")
                trigger=page.locator(f"[data-club-open='{dialog_id}']").first
                trigger.click()
                dialog=page.locator("#"+dialog_id)
                pw.expect(dialog).to_be_visible()
                bounds=dialog.bounding_box()
                assert bounds and bounds["width"]<=min(width,520)+2 and bounds["height"]<=min(height*.92,650)+2
                pw.expect(dialog.locator(".club-dialog__footer")).to_be_visible()
                if dialog_id=="club-voucher":
                    dialog.locator("[data-jalali-calendar-trigger]").click()
                    popover=dialog.locator(".jalali-date__popover--portal")
                    pw.expect(popover).to_be_visible()
                    popover.locator("[role='gridcell']:not(:disabled)").first.click()
                    pw.expect(popover).not_to_be_visible()
                page.keyboard.press("Escape")
                pw.expect(dialog).not_to_be_visible()
                pw.expect(trigger).to_be_focused()
            except Exception as exc:
                errors.append(f"{width}/{dialog_id}: {exc}")
        modal(reverse("staff:detail",args=[staff.pk]),"a.staff-profile-header__btn[href*='book=1']","رزرو نوبت")
        # Booking from a customer profile loads the form on demand, then opens a real modal.
        modal(reverse("customers:detail",args=[customer.pk]),"a.customer-detail-header__btn[href*='book=1']","رزرو نوبت")
        try:
            page.goto(live_server.url+"/app/",wait_until="load")
            if width<1024:
                page.locator(".luna-mobile-account").click()
                pw.expect(page.locator("#mobile-account-sheet")).to_be_visible()
                page.locator("#mobile-account-sheet button[aria-label='بستن']").click()
                pw.expect(page.locator("#mobile-account-sheet")).not_to_be_visible()
            else:
                toggle=page.locator(".luna-sidebar-toggle")
                toggle.click()
                pw.expect(toggle).to_have_attribute("aria-expanded","false")
                toggle.click()
                pw.expect(toggle).to_have_attribute("aria-expanded","true")
                page.locator(".luna-desktop-account").click()
                pw.expect(page.locator("#mobile-account-sheet")).to_be_visible()
                page.keyboard.press("Escape")
                pw.expect(page.locator("#mobile-account-sheet")).not_to_be_visible()
                pw.expect(page.locator(".luna-desktop-account")).to_be_focused()
        except Exception as exc:
            errors.append(f"{width}/navigation interaction: {exc}")
        try:
            external.clear(); js_errors.clear(); broken.clear()
            url=reverse("finance:checkout",args=[customer.pk])+f"?appointment={completed.pk}"
            page.goto(live_server.url+url,wait_until="load")
            pw.expect(page.locator(f"input[name='appointment'][value='{completed.pk}']")).to_be_checked()
            pw.expect(page.locator(".checkout-workspace__totals > div:first-child bdi")).to_have_text("۱٬۲۵۰٬۰۰۰ تومان")
            page.locator("select[name='voucher']").select_option(str(voucher.pk))
            page.locator("input[name='card']").fill("1200000")
            pw.expect(page.locator(".checkout-workspace__balance strong")).to_have_text("۰ تومان")
            page.get_by_role("button",name="ثبت فاکتور و پرداخت").click()
            pw.expect(page.locator(".checkout-workspace__invoice-ref")).to_contain_text("فاکتور")
            assert urlsplit(page.url).path.startswith("/finance/invoices/")
            assert not js_errors and not broken and not external
            page.screenshot(path=str(ARTIFACT/f"{width}-finance-invoice.png"),animations="disabled")
        except Exception as exc:
            errors.append(f"{width}/checkout interaction: {exc}")
        try:
            external.clear(); js_errors.clear(); broken.clear()
            page.goto(live_server.url+reverse("finance:product_sales"),wait_until="load")
            page.locator("select[name='customer']").select_option(str(customer.pk))
            page.locator("select[name='item']").select_option(str(item.pk))
            page.locator("input[name='quantity']").fill("1")
            page.locator("#id_unit_price").fill("250000")
            page.locator("select[name='method']").select_option("card")
            page.get_by_role("button",name="ثبت فروش و رسید").click()
            pw.expect(page.get_by_role("heading",name="رسید پرداخت",exact=True).first).to_be_visible()
            assert "/receipt/" in page.url
            page.get_by_role("link",name="برگشت کالا و وجه").click()
            page.locator("input[name='reason']").fill("تست برگشت کالا")
            page.get_by_role("button",name="ثبت برگشت کالا و وجه").click()
            assert "/receipt/" in page.url
            assert not js_errors and not broken and not external
            page.screenshot(path=str(ARTIFACT/f"{width}-finance-product-return.png"),animations="disabled")
        except Exception as exc:
            errors.append(f"{width}/product return interaction: {exc}")
        context.close()
        browser.close()
    assert not errors, "\n"+"\n".join(errors)
    # The sync Playwright context runs an asyncio loop on the calling thread.
    # Verify persisted state only after the browser context has exited.
    invoice=Invoice.scoped(salon).get()
    assert invoice.received_toman==1200000 and invoice.balance_at_issue_toman==0
    assert Payment.scoped(salon).filter(invoice=invoice).count()==1
    voucher.refresh_from_db()
    assert voucher.invoice_id==invoice.pk and invoice.discount_toman==50000
    sale=ProductSale.scoped(salon).get()
    assert sale.revenue_toman==250000 and sale.cost_toman==150000
    assert Refund.scoped(salon).filter(payment=sale.payment,amount_toman=250000).exists()
    item.refresh_from_db()
    assert item.quantity==4


@pytest.mark.django_db(transaction=True)
def test_overview_populated_notebook_first_fold(live_server, client, owner_membership):
    """Exercise real data, including the maximum 5 staff rows and long currency labels."""
    from apps.accounts.models import User
    from apps.appointments.models import Appointment
    from apps.customers.models import Customer
    from apps.dashboard.role_services import day_bounds
    from apps.finance.models import Payment
    from apps.salons.models import SalonMembership
    from apps.services.models import Service
    from apps.staff.models import StaffProfile

    salon=owner_membership.salon
    day=timezone.localdate()
    start,_=day_bounds(day)
    service=Service.objects.create(salon=salon,name="مراقبت مو",price_toman=12345678)
    for i in range(5):
        membership=owner_membership
        if i:
            user=User.objects.create_user(phone=f"+98912123710{i}")
            membership=SalonMembership.objects.create(salon=salon,user=user,role=SalonMembership.Role.SPECIALIST)
        staff,_=StaffProfile.objects.get_or_create(salon=salon,membership=membership,
            defaults={"display_name":f"متخصص زیبایی شماره {i+1}"})
        customer=Customer.objects.create(salon=salon,full_name=f"مشتری آزمایشی {i+1}",phone=f"+98912123720{i}")
        appointment=Appointment.objects.create(salon=salon,staff=staff,customer=customer,service=service,
            start_at=start+timedelta(hours=8+i),end_at=start+timedelta(hours=8+i,minutes=30),
            completed_at=start+timedelta(hours=8+i,minutes=30),status=Appointment.Status.COMPLETED,price_toman=12345678)
        Payment.objects.create(salon=salon,customer=customer,appointment=appointment,
            total_amount_toman=12345678,paid_amount_toman=12345678,status=Payment.Status.PAID,method=Payment.Method.CARD)

    client.force_login(owner_membership.user)
    session=client.session
    session["active_salon_id"]=str(salon.pk)
    session.save()
    ARTIFACT.mkdir(exist_ok=True)
    with pw.sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True)
        context=browser.new_context(viewport={"width":1366,"height":640},locale="fa-IR",reduced_motion="reduce")
        context.add_cookies([{"name":settings.SESSION_COOKIE_NAME,"value":client.cookies[settings.SESSION_COOKIE_NAME].value,"url":live_server.url}])
        page=context.new_page()
        for trend in (7,30):
            response=page.goto(f"{live_server.url}/app/?day={day.isoformat()}&trend={trend}",wait_until="load")
            assert response.status==200
            page.evaluate("document.fonts.ready")
            pw.expect(page.locator(".overview-staff-list li")).to_have_count(5)
            pw.expect(page.locator(".dashboard-stat-mini")).to_have_count(6)
            pw.expect(page.locator(".overview-chart svg")).to_be_visible()
            for selector in (".overview-kpis",".overview-revenue",".overview-status",".overview-staff",".overview-customers"):
                pw.expect(page.locator(selector)).to_be_in_viewport(ratio=1)
            assert page.evaluate("window.scrollY")==0
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth+2")
            assert page.evaluate("getComputedStyle(document.querySelector('.maison-main')).overflowY === 'visible'")
            page.screenshot(path=str(ARTIFACT/f"1366-overview-populated-{trend}.png"),animations="disabled")
        page.locator(".overview-chart-details summary").click()
        pw.expect(page.locator(".overview-chart-details dl")).to_be_visible()
        assert page.locator(".overview-chart-details").evaluate("(el) => el.open")
        context.close()
        browser.close()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("width,height", [(360,800),(1366,640)])
def test_overview_jalali_direct_month_year_and_day(live_server, client, owner_membership, width, height):
    from urllib.parse import parse_qs
    client.force_login(owner_membership.user)
    session=client.session
    session["active_salon_id"]=str(owner_membership.salon_id)
    session.save()
    with pw.sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True)
        context=browser.new_context(viewport={"width":width,"height":height},locale="fa-IR",reduced_motion="reduce")
        context.add_cookies([{"name":settings.SESSION_COOKIE_NAME,"value":client.cookies[settings.SESSION_COOKIE_NAME].value,"url":live_server.url}])
        page=context.new_page()
        errors=[]
        page.on("pageerror",lambda error:errors.append(str(error)))
        page.goto(live_server.url+"/app/?day=2026-11-20&range=week&trend=30",wait_until="load")
        trigger=page.locator(".dash-page-header__jalali-form [data-jalali-calendar-trigger]")
        pw.expect(trigger).to_contain_text("۱۴۰۵/۰۸/۲۹")
        trigger.click()
        calendar=page.locator(".jalali-date__popover--portal:visible")
        pw.expect(calendar.get_by_role("gridcell",name="۲۹",exact=True)).to_have_attribute("aria-current","date")
        pw.expect(calendar.get_by_label("انتخاب سال",exact=True)).to_have_value("1405")
        pw.expect(calendar.get_by_label("انتخاب ماه",exact=True)).to_have_value("8")

        def assert_compact():
            pw.expect(calendar.get_by_role("button",name="امروز",exact=True)).to_be_in_viewport(ratio=1)
            pw.expect(calendar).to_be_in_viewport(ratio=1)
            assert calendar.evaluate("(el) => el.scrollHeight <= el.clientHeight+1 && el.scrollWidth <= el.clientWidth+1")
            assert calendar.evaluate("(el) => getComputedStyle(el).overflowY") == "visible"

        assert_compact()
        # Exercise a month that requires six calendar rows, not only a short month.
        import jdatetime
        month=next(m for m in range(1,13) if (jdatetime.date(1405,m,1).weekday() + (31 if m<=6 else 30 if m<=11 else 29))>35)
        calendar.get_by_label("انتخاب ماه",exact=True).select_option(str(month))
        pw.expect(calendar.locator(".jalali-date__grid > button")).to_have_count(42)
        pw.expect(calendar.get_by_label("انتخاب ماه", exact=True)).to_have_value(str(month))
        assert_compact()
        calendar.get_by_label("انتخاب سال",exact=True).select_option("1403")
        calendar.get_by_label("انتخاب ماه",exact=True).select_option("12")
        pw.expect(calendar.get_by_role("gridcell",name="۳۰",exact=True)).to_be_enabled()
        with page.expect_navigation(wait_until="load"):
            calendar.get_by_role("gridcell",name="۳۰",exact=True).click()
        assert parse_qs(urlsplit(page.url).query)=={"day":["2025-03-20"],"range":["week"],"trend":["30"]}
        pw.expect(trigger).to_contain_text("۱۴۰۳/۱۲/۳۰")
        trigger.click()
        pw.expect(calendar.get_by_label("انتخاب سال",exact=True)).to_have_value("1403")
        pw.expect(calendar.get_by_label("انتخاب ماه",exact=True)).to_have_value("12")
        assert_compact()
        calendar.get_by_label("انتخاب سال",exact=True).select_option("1404")
        pw.expect(calendar.get_by_role("gridcell",name="۳۰",exact=True)).to_have_count(0)
        calendar.get_by_role("button",name="ماه بعد",exact=True).click()
        pw.expect(calendar.get_by_label("انتخاب سال",exact=True)).to_have_value("1405")
        pw.expect(calendar.get_by_label("انتخاب ماه",exact=True)).to_have_value("1")
        with page.expect_navigation(wait_until="load"):
            calendar.get_by_role("gridcell",name="۱",exact=True).click()
        pw.expect(trigger).to_contain_text("۱۴۰۵/۰۱/۰۱")
        assert parse_qs(urlsplit(page.url).query)["day"]==["2026-03-21"]
        assert not errors
        context.close()
        browser.close()


@pytest.mark.django_db(transaction=True)
def test_staff_board_populated_short_notebook(live_server, client, owner_membership):
    from apps.accounts.models import User
    from apps.salons.models import SalonMembership
    from apps.staff.models import StaffProfile
    from apps.services.models import Service
    salon=owner_membership.salon
    service=Service.objects.create(salon=salon,name="رنگ و لایت",price_toman=2500000)
    for i in range(7):
        membership=owner_membership if i==0 else SalonMembership.objects.create(salon=salon,
            user=User.objects.create_user(phone=f"+98912123180{i}"),role=SalonMembership.Role.SPECIALIST)
        profile,_=StaffProfile.objects.get_or_create(salon=salon,membership=membership)
        profile.display_name=f"متخصص زیبایی {i+1}"
        profile.title="متخصص مو"
        profile.save()
        profile.services.add(service)
    client.force_login(owner_membership.user)
    session=client.session
    session["active_salon_id"]=str(salon.pk)
    session.save()
    ARTIFACT.mkdir(exist_ok=True)
    with pw.sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True)
        context=browser.new_context(viewport={"width":1366,"height":640},locale="fa-IR",reduced_motion="reduce")
        context.add_cookies([{"name":settings.SESSION_COOKIE_NAME,"value":client.cookies[settings.SESSION_COOKIE_NAME].value,"url":live_server.url}])
        page=context.new_page()
        response=page.goto(live_server.url+reverse("staff:list")+"?view=card",wait_until="load")
        assert response.status==200
        page.evaluate("document.fonts.ready")
        pw.expect(page.locator(".staff-board-kpis .suite-kpi")).to_have_count(4)
        pw.expect(page.locator(".suite-staff-card")).to_have_count(6)
        pw.expect(page.locator(".staff-board-card").first.locator(".staff-team-card__stat")).to_have_count(2)
        pw.expect(page.locator(".staff-board-search__submit")).to_be_visible()
        pw.expect(page.locator(".suite-staff-card").nth(5)).to_be_in_viewport(ratio=.5)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth+2")
        assert page.evaluate("getComputedStyle(document.querySelector('.maison-main')).overflowY === 'visible'")
        page.screenshot(path=str(ARTIFACT/"1366-staff-board.png"),animations="disabled")
        page.get_by_role("navigation",name="صفحه‌بندی").get_by_role("link",name="بعدی").click()
        pw.expect(page.locator(".suite-staff-card")).to_have_count(1)
        page.get_by_role("searchbox",name="جست‌وجوی متخصص").fill("زیبایی 1")
        page.get_by_role("button",name="جست‌وجو",exact=True).click()
        pw.expect(page.locator(".suite-staff-card")).to_have_count(1)
        page.set_viewport_size({"width":360,"height":800})
        page.goto(live_server.url+reverse("staff:list")+"?view=card",wait_until="load")
        pw.expect(page.locator(".staff-board-kpis .suite-kpi")).to_have_count(4)
        pw.expect(page.locator(".staff-board-filters")).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth+2")
        page.screenshot(path=str(ARTIFACT/"360-staff-board.png"),animations="disabled")
        page.goto(live_server.url+reverse("finance:overview"),wait_until="load")
        assert page.locator(".maison-app.management-suite").count()==0
        context.close()
        browser.close()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("width,height", [(360,800),(1366,640)])
def test_staff_hours_weekly_editor(live_server, client, owner_membership, browser_data, width, height):
    from apps.staff.models import StaffWorkHours
    salon,staff,_,_,_=browser_data
    client.force_login(owner_membership.user)
    session=client.session
    session["active_salon_id"]=str(salon.pk)
    session.save()
    with pw.sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True)
        context=browser.new_context(viewport={"width":width,"height":height},locale="fa-IR",reduced_motion="reduce")
        context.add_cookies([{"name":settings.SESSION_COOKIE_NAME,"value":client.cookies[settings.SESSION_COOKIE_NAME].value,"url":live_server.url}])
        page=context.new_page()
        errors=[]
        page.on("pageerror",lambda error:errors.append(str(error)))
        page.goto(live_server.url+reverse("staff:hours",args=[staff.pk]),wait_until="load")
        page.evaluate("document.fonts.ready")
        pw.expect(page.locator("[data-hours-day]")).to_have_count(7)
        if width>=1024:
            pw.expect(page.locator(".staff-hours-surface")).to_be_in_viewport(ratio=1)
            pw.expect(page.locator(".staff-hours-form__submit")).to_be_in_viewport(ratio=1)
        page.locator('[data-hours-day="2"]').click()
        pw.expect(page.locator('[data-hours-day="2"]')).to_have_attribute("aria-current","true")
        start=page.locator('[name="start_time"]')
        end=page.locator('[name="end_time"]')
        pw.expect(start).to_have_value("09:00")
        pw.expect(end).to_have_value("18:00")
        start.fill("1030")
        end.fill("1930")
        pw.expect(start).to_have_value("10:30")
        page.get_by_role("button",name="ذخیره برنامهٔ هفتگی").click()
        pw.expect(start).to_have_value("10:30")
        pw.expect(end).to_have_value("19:30")
        page.locator('[name="is_closed"]').check()
        pw.expect(start).to_be_disabled()
        pw.expect(end).to_be_disabled()
        page.get_by_role("button",name="ذخیره برنامهٔ هفتگی").click()
        pw.expect(page.locator('[data-hours-day="2"]')).to_contain_text("تعطیل")

        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth+2")
        assert not errors
        ARTIFACT.mkdir(exist_ok=True)
        page.screenshot(path=str(ARTIFACT/f"{width}-staff-hours.png"),animations="disabled")
        context.close()
        browser.close()
    # Query after Playwright stops its event loop; Django ORM is synchronous.
    assert StaffWorkHours.objects.get(staff=staff,weekday=2).is_closed


@pytest.mark.django_db(transaction=True)
def test_customer_directory_all_eight_cards_visible_at_laptop_height(live_server, client, owner_membership):
    """On 1366px laptops, two rows of customers and pagination fit without internal scrolling."""
    from apps.customers.models import Customer
    salon = owner_membership.salon
    for i in range(9):
        Customer.objects.create(
            salon=salon, full_name=f"مشتری نمایشی شماره {i}", phone=f"+98912800{i:05d}"
        )
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.pk)
    session.save()
    cookie = client.cookies[settings.SESSION_COOKIE_NAME].value
    with pw.sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1366, "height": 640}, locale="fa-IR")
        context.add_cookies([{"name": settings.SESSION_COOKIE_NAME, "value": cookie, "url": live_server.url}])
        page = context.new_page()
        page.goto(live_server.url + reverse("customers:list") + "?view=card", wait_until="load")
        page.evaluate("document.fonts.ready")
        cards = page.locator(".customers-list-card")
        pw.expect(cards).to_have_count(8)
        last = cards.last.bounding_box()
        pager = page.locator(".customers-list-page__pagination").bounding_box()
        assert last is not None and pager is not None
        assert last["y"] + last["height"] <= pager["y"] + 2, "pagination covers last row"
        assert pager["y"] + pager["height"] <= 640, "desktop content exceeds laptop viewport"
        assert page.locator(".customers-list-page--balanced").count() == 1
        assert cards.first.bounding_box()["height"] >= 160, "cards failed to use available desktop height"
        assert 0 <= 640 - (pager["y"] + pager["height"]) <= 52, "excessive empty space remains below pagination"
        assert page.evaluate("getComputedStyle(document.querySelector('.maison-main')).overflowY") == "visible"
        assert page.evaluate("getComputedStyle(document.querySelector('.customers-list-grid')).overflowY") == "visible"
        # A few extra pixels from the shared app shell may scroll; customer cards must not.
        # Visible overflow on auto-sized CSS grid tracks is not clipping.
        # The actual visual contract is: last card is fully above the pager,
        # and both are inside the laptop viewport (asserted immediately above).
        grid_box = page.locator(".customers-list-grid").bounding_box()
        assert grid_box is not None and last["y"] >= grid_box["y"], "customer grid starts beyond its visual bounds"
        context.close()
        browser.close()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("viewport", [{"width": 1366, "height": 660}, {"width": 360, "height": 800}])
def test_services_premium_catalog_layout_and_create_modal(
    live_server, client, owner_membership, viewport
):
    """Nine real service cards, local hero artwork, readable pagination and working create CTA."""
    from apps.services.models import Service
    salon = owner_membership.salon
    for index in range(10):
        Service.objects.create(
            salon=salon, name=f"خدمت زیبایی {index}", price_toman=250_000 + index * 10_000,
        )
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.pk)
    session.save()
    cookie = client.cookies[settings.SESSION_COOKIE_NAME].value
    with pw.sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport=viewport, locale="fa-IR", reduced_motion="reduce")
        context.add_cookies([{"name": settings.SESSION_COOKIE_NAME, "value": cookie, "url": live_server.url}])
        page = context.new_page()
        page.goto(live_server.url + reverse("services:list"), wait_until="load")
        page.evaluate("document.fonts.ready")
        art = page.locator(".services-hero__art img")
        pw.expect(art).to_be_visible()
        assert art.evaluate("(img) => img.complete && img.naturalWidth > 0"), "services hero artwork failed to load"
        cards = page.locator(".services-catalog .services-card")
        pw.expect(cards).to_have_count(9)
        assert page.evaluate("document.scrollingElement.scrollWidth <= innerWidth + 3"), "services have horizontal page overflow"
        if viewport["width"] >= 1024:
            assert page.locator(".services-page--full-grid").count() == 1
            last_card = cards.last.bounding_box()
            pager = page.locator(".services-pagination .suite-pagination").bounding_box()
            assert last_card and pager
            assert last_card["y"] + last_card["height"] <= pager["y"] + 2, "pagination overlaps services"
            assert pager["y"] + pager["height"] <= viewport["height"] + 2, "pagination below desktop viewport"
            assert cards.first.bounding_box()["height"] >= 90
        page.locator(".services-hero__add").click()
        pw.expect(page.get_by_role("dialog", name="افزودن خدمت")).to_be_visible()
        context.close()
        browser.close()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("width", [1366, 820, 390])
def test_customer_table_column_alignment_and_mobile_rows(live_server, client, owner_membership, width):
    """Headers, phone numbers, visits, and actions stay in their own RTL tracks."""
    from apps.customers.models import Customer

    salon = owner_membership.salon
    Customer.objects.create(salon=salon, full_name="مشتری ویژه برای بررسی جدول", phone="+989121222333")
    Customer.objects.create(salon=salon, full_name="نام کوتاه", phone="+989121222334")
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.pk)
    session.save()
    cookie = client.cookies[settings.SESSION_COOKIE_NAME].value

    with pw.sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": width, "height": 790}, locale="fa-IR")
        context.add_cookies([{"name": settings.SESSION_COOKIE_NAME, "value": cookie, "url": live_server.url}])
        page = context.new_page()
        page.goto(live_server.url + reverse("customers:list") + "?view=table", wait_until="load")
        page.evaluate("document.fonts.ready")
        table = page.locator(".customers-list-table")
        rows = table.locator("tbody tr")
        assert rows.count() >= 2
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 3"), "customer table overflows viewport"
        first = rows.first
        assert first.locator(".customers-list-table__phone-value").get_attribute("dir") == "ltr"
        pw.expect(first.locator(".customers-list-table__profile-link")).to_be_visible()
        if width > 900:
            assert table.evaluate("(el) => getComputedStyle(el).tableLayout") == "fixed"
            for col in range(4):
                th = table.locator("thead th").nth(col).bounding_box()
                td = first.locator("td").nth(col).bounding_box()
                assert th and td
                assert abs(th["x"] - td["x"]) <= 2, f"column {col} header/body left edges diverged"
                assert abs(th["width"] - td["width"]) <= 2, f"column {col} header/body widths diverged"
            name = first.locator(".customers-list-table__name").bounding_box()
            phone = first.locator(".customers-list-table__phone").bounding_box()
            visits = first.locator(".customers-list-table__visits").bounding_box()
            action = first.locator(".customers-list-table__action").bounding_box()
            assert name["x"] > phone["x"] > visits["x"] > action["x"], "RTL column order incorrect"
        else:
            assert table.evaluate("(el) => getComputedStyle(el).display") == "block"
            assert table.locator("thead").evaluate("(el) => getComputedStyle(el).display") == "none"
            assert first.locator(".customers-list-table__phone").is_visible()
            assert first.evaluate("(el) => getComputedStyle(el).display") == "grid"
        context.close()
        browser.close()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("width,height", [(1366,640),(390,800)])
def test_staff_directory_viewport_fit_and_pagination(live_server, client, owner_membership, width, height):
    """Full desktop staff page balances both rows; small screens keep natural scrolling."""
    from django.contrib.auth import get_user_model
    from apps.salons.models import SalonMembership
    from apps.staff.models import StaffProfile

    salon = owner_membership.salon
    for index in range(9):
        user = get_user_model().objects.create_user(
            phone=f"+98912567{index:04d}", full_name=f"متخصص نمایشی {index}"
        )
        membership = SalonMembership.objects.create(
            salon=salon, user=user, role=SalonMembership.Role.SPECIALIST
        )
        StaffProfile.objects.create(
            salon=salon, membership=membership,
            display_name=f"متخصص زیبایی {index}", title="میکاپ و آرایش"
        )
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.pk)
    session.save()
    cookie = client.cookies[settings.SESSION_COOKIE_NAME].value

    with pw.sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": width, "height": height}, locale="fa-IR",
            reduced_motion="reduce",
        )
        context.add_cookies([{
            "name": settings.SESSION_COOKIE_NAME,
            "value": cookie, "url": live_server.url,
        }])
        page = context.new_page()
        page.goto(live_server.url + reverse("staff:list") + "?view=card", wait_until="load")
        page.evaluate("document.fonts.ready")
        board = page.locator(".staff-board-v2")
        cards = board.locator(".staff-board-card")
        pw.expect(cards).to_have_count(6)
        pw.expect(board.locator(".staff-board-kpis .suite-kpi")).to_have_count(4)
        pw.expect(board.locator(".staff-team-page__add")).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 3"), "staff directory horizontal overflow"
        assert page.evaluate("getComputedStyle(document.querySelector('.staff-board-grid')).overflowY === 'visible'"), "staff grid nested scrollbar"
        if width >= 1200:
            assert board.evaluate("(el) => el.classList.contains('staff-board-v2--balanced')")
            cols = cards.first.evaluate("(el) => getComputedStyle(el.parentElement).gridTemplateColumns.split(' ').length")
            assert cols == 3
            first = cards.first.bounding_box()
            last = cards.last.bounding_box()
            pager = board.locator(".staff-board-pagination").bounding_box()
            assert first and last and pager
            assert last["y"] + last["height"] <= pager["y"] + 3, "last staff row overlaps pagination"
            assert pager["y"] + pager["height"] <= height + 2, "staff pagination off viewport"
            assert 0 <= height - pager["y"] - pager["height"] <= 52, "excessive blank space below staff pagination"
            assert cards.first.bounding_box()["height"] >= 150, "staff rows too short"
        else:
            assert cards.first.bounding_box()["height"] >= 150
            assert board.locator(".staff-board-kpis").is_visible()
        table_response = page.goto(
            live_server.url + reverse("staff:list") + "?view=table",
            wait_until="load",
        )
        assert table_response and table_response.status == 200
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 3")
        if width >= 1200:
            assert page.locator(".staff-board-v2--table-balanced").count() == 1
            pw.expect(page.locator(".staff-team-table .maison-table tbody tr")).to_have_count(6)
            pager = page.locator(".staff-board-pagination").bounding_box()
            assert pager and pager["y"] + pager["height"] <= height + 2
        context.close()
        browser.close()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("width,height", [(1366,768),(390,800)])
def test_finance_payment_modal_amount_partition_alignment(
    live_server, client, owner_membership, width, height,
):
    """Payment amount inputs share a baseline on desktop and stack cleanly on phones."""
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(owner_membership.salon_id)
    session.save()
    cookie = client.cookies[settings.SESSION_COOKIE_NAME].value

    with pw.sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": width, "height": height}, locale="fa-IR",
            reduced_motion="reduce",
        )
        context.add_cookies([{
            "name": settings.SESSION_COOKIE_NAME, "value": cookie,
            "url": live_server.url,
        }])
        page = context.new_page()
        page.goto(live_server.url + reverse("finance:overview")
                  + "?tab=cash&range=today&payment=1", wait_until="load")
        dialog = page.get_by_role("dialog", name="ثبت پرداخت مشتری")
        pw.expect(dialog).to_be_visible()
        amounts = dialog.locator(".finance-payment-form__fields--amounts")
        fields = amounts.locator(":scope > .finance-payment-form__field")
        pw.expect(fields).to_have_count(3)
        assert "برای نوبت دارای بیعانه" not in dialog.inner_text()
        boxes = [field.locator("input").bounding_box() for field in fields.all()]
        assert all(boxes)
        if width >= 640:
            assert max(b["y"] for b in boxes) - min(b["y"] for b in boxes) <= 3, "amount fields do not align"
            assert max(b["width"] for b in boxes) - min(b["width"] for b in boxes) <= 3, "unequal amount widths"
        else:
            assert boxes[0]["y"] < boxes[1]["y"] < boxes[2]["y"], "mobile amounts not stacked"
        assert dialog.evaluate("(el) => el.scrollWidth <= el.clientWidth + 2"), "payment modal overflows horizontally"
        context.close()
        browser.close()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("width,height", [(390,800), (1366,768)])
def test_womens_onboarding_advances_in_real_browser(live_server, client, width, height):
    """A women's salon with a Persian name completes both first wizard steps."""
    from apps.accounts.models import User
    from apps.salons.models import Salon

    user = User.objects.create_user(phone=f"+989121{width:06d}", full_name="مدیر سالن")
    client.force_login(user)
    cookie = client.cookies[settings.SESSION_COOKIE_NAME].value
    with pw.sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": width, "height": height},
            locale="fa-IR", reduced_motion="reduce",
        )
        context.add_cookies([{
            "name": settings.SESSION_COOKIE_NAME, "value": cookie, "url": live_server.url,
        }])
        page = context.new_page()
        response = page.goto(
            live_server.url + reverse("salons_onboarding:wizard", kwargs={"step": 1}),
            wait_until="load",
        )
        assert response and response.status == 200
        assert page.locator('input[name="business_type"]').count() == 0
        assert page.get_by_role("heading", name="اطلاعات اولیه سالن").is_visible()
        page.get_by_label("نام سالن").fill("سالن زیبایی نورا")
        page.get_by_role("button", name="ادامه").click()
        page.wait_for_url("**/onboarding/wizard/2/")
        assert page.get_by_role("heading", name="هویت سالن").is_visible()
        slug = page.locator("#id_slug")
        assert slug.input_value().isascii() and slug.input_value().startswith("salon-")
        page.locator("#id_public_phone").fill("09121112233")
        page.get_by_role("button", name="ادامه").click()
        page.wait_for_url("**/onboarding/wizard/3/")
        assert page.get_by_role("heading", name="خدمات سالن").is_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 3")
        context.close()
        browser.close()

    assert Salon.objects.get(name="سالن زیبایی نورا").business_type == Salon.BusinessType.BEAUTY_WOMEN


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("width,height", [(390,800), (1366,768)])
def test_staff_invite_specialty_select_shows_saved_salon_services(
    live_server, client, owner_membership, width, height,
):
    """The invited specialist's specialty is a dropdown backed by salon services."""
    from apps.services.models import Service
    from apps.salons.models import SalonInvitation

    salon = owner_membership.salon
    first = Service.objects.create(salon=salon, name="رنگ و لایت")
    second = Service.objects.create(salon=salon, name="ناخن")
    Service.objects.create(salon=salon, name="غیرفعال", is_active=False)
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
            "name": settings.SESSION_COOKIE_NAME, "value": cookie, "url": live_server.url,
        }])
        page = context.new_page()
        page.goto(live_server.url + reverse("staff:list") + "?create=1", wait_until="load")
        modal = page.get_by_role("dialog", name="افزودن متخصص")
        pw.expect(modal).to_be_visible()
        specialty = modal.locator('select[name="specialty"]')
        pw.expect(specialty).to_be_visible()
        option_names = specialty.locator("option").all_text_contents()
        assert "رنگ و لایت" in option_names and "ناخن" in option_names
        assert "غیرفعال" not in option_names
        assert len(option_names) == 3
        modal.locator('input[name="first_name"]').fill("مریم")
        modal.locator('input[name="last_name"]').fill("امینی")
        modal.locator('input[name="phone"]').fill("09123459877")
        specialty.select_option(str(second.pk))
        modal.get_by_role("button", name="ارسال دعوت").click()
        page.wait_for_url("**/staff/", wait_until="load")
        context.close()
        browser.close()

    invitation = SalonInvitation.objects.get(salon=salon, phone="+989123459877")
    assert invitation.invitee_service_id == second.pk


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("width,height", [(390,800), (1366,768)])
def test_modal_image_choose_button_hides_native_file_control_and_works(
    live_server, client, owner_membership, width, height,
):
    """Customer and service dialogs show only the localized image picker."""
    from io import BytesIO
    from PIL import Image
    from apps.services.models import Service

    salon = owner_membership.salon
    service = Service.objects.create(salon=salon, name="رنگ و لایت")
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.pk)
    session.save()
    cookie = client.cookies[settings.SESSION_COOKIE_NAME].value
    payload = BytesIO()
    Image.new("RGB", (8, 8), "white").save(payload, "PNG")
    file_data = {
        "name": "salon-photo.png", "mimeType": "image/png",
        "buffer": payload.getvalue(),
    }
    with pw.sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": width, "height": height},
            locale="fa-IR", reduced_motion="reduce",
        )
        context.add_cookies([{
            "name": settings.SESSION_COOKIE_NAME, "value": cookie,
            "url": live_server.url,
        }])
        page = context.new_page()
        for route, query, form_id, cls in (
            ("customers:list", "?create=1", "customer-create-form", "customer-form-file__btn"),
            ("services:list", "?create=1", "service-create-form", "service-form-file__btn"),
            ("services:list", f"?edit={service.pk}", "service-edit-form", "service-form-file__btn"),
        ):
            response = page.goto(live_server.url + reverse(route) + query, wait_until="load")
            assert response and response.status == 200
            form = page.locator(f"#{form_id}")
            pw.expect(form).to_be_visible()
            if route == "services:list":
                form.get_by_role("button", name="تنظیمات بیشتر").click()
            else:
                form.get_by_role("button", name="اطلاعات تکمیلی").click()
            label = form.locator(f"label.{cls}")
            pw.expect(label).to_be_visible()
            assert label.inner_text().strip() == "انتخاب تصویر"
            native = label.locator("input[type=file]")
            pw.expect(native).to_have_count(1)
            dimensions = native.evaluate("""(el) => {
                const css=getComputedStyle(el), b=el.getBoundingClientRect();
                return [css.position, css.opacity, css.display, b.width, b.height];
            }""")
            assert dimensions[0:2] == ["absolute", "0"]
            assert dimensions[2] != "none" and dimensions[3] <= 2 and dimensions[4] <= 2
            with page.expect_file_chooser() as pending:
                label.click()
            pending.value.set_files(file_data)
            assert native.evaluate("(el) => el.files[0].name") == "salon-photo.png"
            # Alpine updates the filename in a reactive microtask after the
            # browser's file chooser resolves. Wait for the actual UI state.
            name_selector = (".customer-form-file__name" if route == "customers:list"
                             else ".service-form-file__name")
            pw.expect(form.locator(name_selector)).to_have_text("salon-photo.png")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 3")
        context.close()
        browser.close()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("width,height", [(1280,720), (1366,768), (390,800)])
def test_checkout_editorial_customer_selection_and_invoice_workflow(
    live_server, client, owner_membership, width, height,
):
    """Real browser: compact selection, live totals, safe issue and thank-you."""
    from apps.appointments.models import Appointment
    from apps.customers.models import Customer
    from apps.finance.models import Invoice
    from apps.services.models import Service
    from apps.staff.models import StaffProfile

    salon = owner_membership.salon
    customers = [
        Customer.objects.create(
            salon=salon, full_name=f"مشتری زیبایی {index}",
            phone=f"+989121980{index:04d}",
        )
        for index in range(7)
    ]
    customer = customers[0]
    staff, _ = StaffProfile.objects.get_or_create(
        salon=salon, membership=owner_membership,
    )
    service = Service.objects.create(
        salon=salon, name="رنگ و لایت", price_toman=800000,
    )
    now = timezone.now()
    appt = Appointment.objects.create(
        salon=salon, customer=customer, staff=staff, service=service,
        status=Appointment.Status.COMPLETED,
        start_at=now - timedelta(days=1),
        end_at=now - timedelta(days=1) + timedelta(minutes=50),
        completed_at=now, price_toman=800000,
    )
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
            "value": cookie, "url": live_server.url,
        }])
        page = context.new_page()
        search_url = live_server.url + reverse("finance:checkout_customers")
        response = page.goto(search_url, wait_until="load")
        assert response and response.status == 200
        pw.expect(page.get_by_role("heading", name="صدور فاکتور")).to_be_visible()
        pw.expect(page.locator(".checkout-workspace__customer-row")).to_have_count(6)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 3")
        if width >= 1100:
            assert page.locator(".checkout-workspace__paper").bounding_box()["y"] < height
            assert page.locator(".checkout-workspace__gratitude").bounding_box()["y"] < height

        # Search is functional and not just a visual mockup.
        page.locator("#checkout-search").fill("مشتری زیبایی 0")
        page.get_by_role("button", name="جستجو").click()
        pw.expect(page.locator(".checkout-workspace__customer-row")).to_have_count(1)
        page.locator(".checkout-workspace__customer-row").click()
        page.wait_for_url("**/finance/checkout/*/")
        invoice_form = page.locator("form.checkout-workspace__invoice")
        pw.expect(invoice_form).to_be_visible()
        pw.expect(page.locator(".checkout-workspace__table tbody tr")).to_have_count(1)
        assert "پیش‌نویس فاکتور" in invoice_form.inner_text()
        assert "رنگ و لایت" in invoice_form.inner_text()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 3")
        if width >= 1100:
            assert invoice_form.bounding_box()["y"] + invoice_form.bounding_box()["height"] <= height + 3, "ordinary invoice extends beyond desktop viewport"

        checkbox = invoice_form.locator(f'input[name="appointment"][value="{appt.pk}"]')
        checkbox.check()
        cash = invoice_form.locator('input[name="cash"]')
        cash.fill("200000")
        assert "تومان" in invoice_form.locator(".checkout-workspace__balance strong").inner_text()
        invoice_form.get_by_role("button", name="ثبت فاکتور و پرداخت").click()
        page.wait_for_url("**/finance/invoices/*/")
        assert page.locator(".checkout-workspace--issued").count() == 1
        assert "از اعتماد شما سپاسگزاریم" in page.locator(".checkout-workspace__gratitude").inner_text()
        assert "چاپ / ذخیره PDF" in page.locator(".checkout-workspace__invoice-actions").inner_text()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 3")
        context.close()
        browser.close()

    issued = Invoice.scoped(salon).get(customer=customer)
    assert issued.gross_toman == 800000
    assert issued.received_toman == 200000
    assert issued.balance_at_issue_toman == 600000


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("width,height", [(390,800), (1366,768)])
def test_shared_jalali_birth_picker_has_equal_month_year_cards_and_working_days(
    live_server, client, owner_membership, width, height,
):
    """The customer birthday calendar shares the Editorial Rose geometry on mobile and desktop."""
    import jdatetime

    client.force_login(owner_membership.user)
    session=client.session
    session["active_salon_id"]=str(owner_membership.salon_id)
    session.save()
    with pw.sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True)
        context=browser.new_context(
            viewport={"width":width,"height":height},
            locale="fa-IR",reduced_motion="reduce",
        )
        context.add_cookies([{
            "name":settings.SESSION_COOKIE_NAME,
            "value":client.cookies[settings.SESSION_COOKIE_NAME].value,
            "url":live_server.url,
        }])
        page=context.new_page()
        errors=[]
        page.on("pageerror",lambda error:errors.append(str(error)))
        response=page.goto(
            live_server.url+reverse("customers:list")+"?create=1",
            wait_until="load",
        )
        assert response and response.status==200
        form=page.locator("#customer-create-form")
        pw.expect(form).to_be_visible()
        form.get_by_role("button",name="اطلاعات تکمیلی").click()
        trigger=form.locator('[data-jalali-calendar-trigger]')
        pw.expect(trigger).to_be_visible()
        trigger.click()
        calendar=page.locator(".jalali-date__popover--portal:visible")
        pw.expect(calendar).to_be_visible()
        pw.expect(calendar).to_have_class("jalali-date__popover jalali-date__popover--portal jalali-date__popover--birth")
        month=calendar.get_by_label("ماه",exact=True)
        year=calendar.get_by_label("سال",exact=True)
        pw.expect(month).to_be_visible()
        pw.expect(year).to_be_visible()
        mb=month.bounding_box()
        yb=year.bounding_box()
        assert mb and yb
        assert abs(mb["width"]-yb["width"])<=1, (width,mb,yb)
        assert abs(mb["height"]-yb["height"])<=1, (width,mb,yb)
        assert 38<=mb["height"]<=42, mb
        assert abs(mb["y"]-yb["y"])<=1
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 3")
        box=calendar.bounding_box()
        assert box and box["x"]>=0 and box["x"]+box["width"]<=width+1
        assert box["y"]>=0 and box["y"]+box["height"]<=height+1

        year.fill("1403")
        year.press("Tab")
        month.select_option("7")
        pw.expect(month).to_have_value("7")
        pw.expect(year).to_have_value("1403")
        dates=calendar.locator('.jalali-date__grid button[role="gridcell"]:not([disabled])')
        assert dates.count()==30
        dates.first.click()
        pw.expect(calendar).not_to_be_visible()
        selected=form.locator('[name="birth_date"]')
        expected=jdatetime.date(1403,7,1).togregorian().isoformat()
        pw.expect(selected).to_have_value(expected)
        assert not errors, errors
        context.close()
        browser.close()


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("width,height", [(360,800), (1366,640)])
def test_shared_jalali_direct_selects_have_identical_card_geometry(
    live_server, client, owner_membership, width, height,
):
    """The same sizing applies to month/year controls in overview and finance pickers."""
    client.force_login(owner_membership.user)
    session=client.session
    session["active_salon_id"]=str(owner_membership.salon_id)
    session.save()
    with pw.sync_playwright() as playwright:
        browser=playwright.chromium.launch(headless=True)
        context=browser.new_context(
            viewport={"width":width,"height":height},
            locale="fa-IR",reduced_motion="reduce",
        )
        context.add_cookies([{
            "name":settings.SESSION_COOKIE_NAME,
            "value":client.cookies[settings.SESSION_COOKIE_NAME].value,
            "url":live_server.url,
        }])
        page=context.new_page()
        response=page.goto(
            live_server.url+"/app/?day=2026-11-20&range=week&trend=30",
            wait_until="load",
        )
        assert response and response.status==200
        page.locator(".dash-page-header__jalali-form [data-jalali-calendar-trigger]").click()
        calendar=page.locator(".jalali-date__popover--portal:visible")
        pw.expect(calendar).to_be_visible()
        month=calendar.get_by_label("انتخاب ماه",exact=True)
        year=calendar.get_by_label("انتخاب سال",exact=True)
        mb=month.bounding_box()
        yb=year.bounding_box()
        assert mb and yb
        assert abs(mb["width"]-yb["width"])<=1
        assert abs(mb["height"]-yb["height"])<=1
        assert 38<=mb["height"]<=42
        assert calendar.evaluate("(el) => el.scrollHeight <= el.clientHeight+2")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth+3")
        calendar.get_by_role("button",name="ماه قبل").click()
        pw.expect(month).to_have_value("7")
        pw.expect(year).to_have_value("1405")
        context.close()
        browser.close()

@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("width,height", [(390,800), (1280,720)])
def test_owner_onboarding_modal_later_resume_in_browser(
    live_server, client, owner_membership, width, height
):
    """New owners see the guided setup inside their dashboard; deferral reopens at the saved step."""
    salon = owner_membership.salon
    salon.settings.onboarding_completed_at = None
    salon.settings.save(update_fields=["onboarding_completed_at"])
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()

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
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        result = page.goto(live_server.url + reverse("dashboard:home"), wait_until="load")
        assert result and result.status == 200
        dialog = page.get_by_role("dialog", name="راه‌اندازی سالن شما")
        pw.expect(dialog).to_be_visible()
        pw.expect(page.locator('[data-onboarding-step="1"]')).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth+3")
        dialog.locator('input[name="name"]').fill("سالن زیبایی نیلوفر")
        dialog.get_by_role("button", name="ادامه", exact=True).click()
        pw.expect(page.locator('[data-onboarding-step="2"]')).to_be_visible()
        dialog.locator("[data-onboarding-later]").click()
        pw.expect(dialog).not_to_be_visible()
        page.goto(live_server.url + reverse("dashboard:home"), wait_until="load")
        pw.expect(page.get_by_role("dialog", name="راه‌اندازی سالن شما")).not_to_be_visible()
        page.goto(live_server.url + reverse("salons_settings:home"), wait_until="load")
        page.locator("[data-open-salon-onboarding]").click()
        pw.expect(page.locator('[data-onboarding-step="2"]')).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth+3")
        assert not errors, errors
        context.close()
        browser.close()
