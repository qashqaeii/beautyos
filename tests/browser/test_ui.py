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
@pytest.mark.parametrize("width,height", [(360,800),(768,1024),(1440,900)])
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
        ("finance","/finance/"),("finance-debts","/finance/?tab=debts"),("finance-cash","/finance/?tab=cash"),("finance-reports","/finance/?tab=reports"),("finance-receipts","/finance/?tab=receipts"),
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
                        assert page.evaluate("getComputedStyle(document.querySelector('#workspace-sidebar-nav')).overflowY === 'visible'"), "nested sidebar scroll"
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2"), "horizontal page overflow"
                assert not external, f"external runtime requests {external}"
                assert not broken, f"broken static assets {broken}"
                assert not js_errors, f"JavaScript exceptions {js_errors}"
                if name in {"home","login","overview","management","reception","calendar","customer-detail","staff-detail","services","finance","packages","inventory","loyalty","storefront"}:
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
            except Exception as exc:
                errors.append(f"1366/overview or loyalty first viewport: {exc}")
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
                footer = dialog.locator(".inventory-create-modal__foot")
                pw.expect(footer).to_be_visible()
                footer_box = footer.bounding_box()
                assert footer_box and footer_box["y"] + footer_box["height"] <= box["y"] + box["height"] + 2
                assert dialog.evaluate("(el) => getComputedStyle(el, '::before').content === 'none' || getComputedStyle(el, '::before').display === 'none'"), "decorative modal panel still present"
                page.screenshot(path=str(ARTIFACT/f"{width}-modal-{name}.png"),animations="disabled")
                page.keyboard.press("Escape")
                pw.expect(dialog).not_to_be_visible(timeout=6000)
            except Exception as exc:
                errors.append(f"{width}/{name} interaction: {exc}")
        modal("/customers/",".customers-list-page__add","مشتری جدید")
        modal("/staff/",".staff-team-page__add","افزودن متخصص")
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
            pw.expect(page.locator(".finance-checkout-wrap .fin-line bdi")).to_have_text("۱٬۲۵۰٬۰۰۰ تومان")
            page.locator("select[name='voucher']").select_option(str(voucher.pk))
            page.locator("input[name='card']").fill("1200000")
            pw.expect(page.locator(".finance-checkout-wrap .fin-received-total strong")).to_have_text("۰ تومان")
            page.get_by_role("button",name="ثبت فاکتور و پرداخت").click()
            pw.expect(page.get_by_role("heading",name="فاکتور خدمات",exact=True)).to_be_visible()
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
