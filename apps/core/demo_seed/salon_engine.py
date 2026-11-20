"""Comprehensive women's demo salon dataset — demo-salon-a only."""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal

import jdatetime
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.appointments.models import Appointment
from apps.appointments.services.lifecycle import complete_appointment
from apps.appointments.services.scheduling import SchedulingError, create_appointment
from apps.commissions.models import CommissionRule
from apps.commissions.services import create_settlement
from apps.core.demo_seed.engine import DemoSeedEngine, SALON_A_SLUG, demo_customer_phone
from apps.core.demo_seed.salon_avatars import solid_avatar_file
from apps.core.demo_seed.salon_dataset import (
    CAMPAIGNS,
    CUSTOMER_TAGS,
    CUSTOMERS,
    DEMO_SALON_MARKER,
    LOYALTY_REWARDS,
    NOTES,
    PACKAGE_DEFS,
    PRODUCTS,
    SERVICE_ROWS,
    SPECIALISTS,
    specialist_phone,
)
from apps.core.demo_seed.salon_reset import reset_demo_salon
from apps.core.utils.dates import jalali_month_bounds
from apps.customers.models import Customer, CustomerNote, CustomerTag
from apps.customers.services import refresh_customer_stats
from apps.expenses.models import Expense
from apps.finance.cash_close import close_cash_day
from apps.finance.checkout import issue_invoice
from apps.finance.ledger import refund_payment
from apps.finance.models import FinancialAccount, Payment, RecurringExpense, SalonDebt, StaffAgreement
from apps.finance.periods import create_agreement, open_staff_period, pay_staff_period
from apps.finance.services import create_appointment_deposit
from apps.finance.stock_finance import consume_material, sell_product, set_unit_cost
from apps.inventory.models import InventoryCategory, InventoryItem
from apps.inventory.services import create_inventory_item
from apps.loyalty.benefits import register_referral
from apps.loyalty.memberships import buy_membership
from apps.loyalty.models import LoyaltyPolicy, LoyaltyReward, ledger_add_points, ledger_redeem_points
from apps.loyalty.rewards import redeem_reward
from apps.packages.models import ServicePackage
from apps.portfolio.models import PortfolioItem
from apps.retention.campaigns import create_campaign, prepare_campaign
from apps.retention.models import Campaign, FollowUp
from apps.salons.models import Salon, SalonMembership, SalonSettings
from apps.services.models import Service, ServiceCategory
from apps.staff.models import StaffProfile, StaffWorkHours
from apps.waitlist.models import WaitlistEntry

REQUEST_NS = uuid.UUID("f47ac10b-58cc-4372-a567-0e02b2c3d479")


def _req_key(label: str) -> uuid.UUID:
    return uuid.uuid5(REQUEST_NS, f"{DEMO_SALON_MARKER}:{label}")


def _jalali_to_gregorian(year: int, month: int, day: int) -> date:
    return jdatetime.date(year, month, day).togregorian()


@dataclass
class SalonSeedPlan:
    actions: list[str] = field(default_factory=list)

    def log(self, msg: str):
        self.actions.append(msg)


class DemoSalonSeedEngine:
    def __init__(self, *, dry_run: bool = False, stdout=None):
        self.dry_run = dry_run
        self.stdout = stdout
        self.plan = SalonSeedPlan()
        random.seed(20251120)

    def _say(self, msg: str):
        if self.stdout:
            self.stdout.write(msg)
        self.plan.log(msg)

    def run(self, *, reset_first: bool = False):
        if self.dry_run:
            self._say("dry-run: comprehensive salon seed planned")
            return self.plan

        base = DemoSeedEngine(dry_run=False, stdout=self.stdout)
        owner, salon = base._ensure_salon(SALON_A_SLUG)
        if salon.business_type != salon.BusinessType.BEAUTY_WOMEN:
            salon.business_type = salon.BusinessType.BEAUTY_WOMEN
            salon.save(update_fields=["business_type", "updated_at"])

        if reset_first:
            self._say("reset demo-salon transactional data")
            reset_demo_salon(salon)

        with transaction.atomic():
            policy = self._ensure_loyalty_policy(salon)
            staff_by_spec = self._seed_specialists(salon, owner)
            self._seed_agreements(salon, staff_by_spec, owner)
            services = self._seed_services(salon, staff_by_spec)
            customers = self._seed_customers(salon)
            items = self._seed_inventory(salon, owner)
            self._seed_accounts(salon)
            self._seed_expenses(salon)
            packages = self._seed_packages(salon)
            self._seed_loyalty_catalog(salon)
            appts = self._seed_appointments(salon, owner, customers, staff_by_spec, services)
            self._seed_finance_flows(salon, owner, customers, appts, items)
            self._seed_loyalty_members(salon, customers, packages, owner)
            self._seed_marketing(salon, owner, customers)
            self._seed_staff_payroll(salon, staff_by_spec, owner)
            self._seed_portfolio(salon)
            self._seed_waitlist(salon, customers, services)
            stats = self._verify(salon, customers, services, appts)
            self._say(f"demo salon seed complete — {stats}")

        return self.plan

  # ——— setup ———

    def _ensure_loyalty_policy(self, salon: Salon) -> LoyaltyPolicy:
        row, _ = LoyaltyPolicy.objects.get_or_create(salon=salon)
        row.enabled = True
        row.spend_per_point_toman = 50_000
        row.visit_points = 25
        row.birthday_points = 80
        row.referral_points = 120
        row.save()
        return row

    def _seed_specialists(self, salon: Salon, owner: User) -> dict[str, StaffProfile]:
        out: dict[str, StaffProfile] = {}
        for i, spec in enumerate(SPECIALISTS, start=1):
            phone = specialist_phone(i)
            user, _ = User.objects.get_or_create(phone=phone, defaults={"full_name": spec["full_name"]})
            if user.full_name != spec["full_name"]:
                user.full_name = spec["full_name"]
                user.save(update_fields=["full_name", "updated_at"])
            mem, _ = SalonMembership.objects.get_or_create(
                user=user,
                salon=salon,
                defaults={"role": SalonMembership.Role.SPECIALIST},
            )
            staff, created = StaffProfile.objects.get_or_create(
                salon=salon,
                membership=mem,
                defaults={
                    "display_name": spec["full_name"],
                    "title": spec["title"],
                    "bio": f"{DEMO_SALON_MARKER} · {spec['years']} سال سابقه در {spec['specialty']}",
                    "is_bookable": True,
                    "calendar_color": spec["color"],
                },
            )
            if not staff.bio.startswith(DEMO_SALON_MARKER):
                staff.bio = f"{DEMO_SALON_MARKER} · {spec['years']} سال سابقه در {spec['specialty']}"
            staff.title = spec["title"]
            staff.calendar_color = spec["color"]
            staff.is_active = True
            staff.is_bookable = True
            if not staff.avatar:
                staff.avatar.save(
                    f"demo-staff-{i}.png",
                    solid_avatar_file(f"staff-{i}", spec["color"]),
                    save=False,
                )
            staff.save()
            for weekday in range(6):
                StaffWorkHours.objects.get_or_create(
                    salon=salon,
                    staff=staff,
                    weekday=weekday,
                    defaults={"start_time": time(9, 0), "end_time": time(20, 30)},
                )
            StaffWorkHours.objects.get_or_create(
                salon=salon,
                staff=staff,
                weekday=6,
                defaults={"is_closed": True, "start_time": time(0, 0), "end_time": time(0, 0)},
            )
            out[spec["specialty"]] = staff
        self._say(f"specialists: {len(out)}")
        return out

    def _seed_agreements(self, salon: Salon, staff_map: dict[str, StaffProfile], actor: User):
        month_start, _ = jalali_month_bounds(timezone.localdate() - timedelta(days=120))
        for spec in SPECIALISTS:
            staff = staff_map[spec["specialty"]]
            mode, amount = spec["agreement"]
            if StaffAgreement.scoped(salon).filter(staff=staff, effective_month=month_start).exists():
                continue
            try:
                create_agreement(
                    salon=salon,
                    staff_id=staff.pk,
                    month=month_start,
                    mode=mode,
                    amount=amount,
                    actor=actor,
                )
            except Exception:
                StaffAgreement.objects.get_or_create(
                    salon=salon,
                    staff=staff,
                    effective_month=month_start,
                    defaults={"mode": mode, "monthly_toman": amount},
                )

        CommissionRule.objects.get_or_create(
            salon=salon,
            name=f"{DEMO_SALON_MARKER} پایه ۳۵٪",
            defaults={"percent": 35, "is_active": True},
        )
        for spec in SPECIALISTS[:4]:
            staff = staff_map[spec["specialty"]]
            CommissionRule.objects.get_or_create(
                salon=salon,
                staff=staff,
                service=None,
                defaults={"name": f"{DEMO_SALON_MARKER} {spec['full_name']}", "percent": 40, "is_active": True},
            )

    def _seed_services(self, salon: Salon, staff_map: dict[str, StaffProfile]) -> list[Service]:
        services: list[Service] = []
        sort = 0
        for specialty, name, duration, price in SERVICE_ROWS:
            sort += 1
            cat, _ = ServiceCategory.objects.get_or_create(salon=salon, name=specialty, defaults={"sort_order": sort})
            staff = staff_map.get(specialty)
            svc, _ = Service.objects.get_or_create(
                salon=salon,
                name=name,
                defaults={
                    "category": cat,
                    "price_toman": price,
                    "duration_minutes": duration,
                    "description": f"{DEMO_SALON_MARKER}|{specialty}",
                    "is_public": True,
                    "sort_order": sort,
                },
            )
            if staff:
                staff.services.add(svc)
            services.append(svc)
        self._say(f"services: {len(services)}")
        return services

    def _seed_customers(self, salon: Salon) -> list[Customer]:
        today = timezone.localdate()
        j_today = jdatetime.date.fromgregorian(date=today)
        tags = {n: CustomerTag.objects.get_or_create(salon=salon, name=n, defaults={"color": c})[0] for n, c in CUSTOMER_TAGS.items()}
        customers: list[Customer] = []
        for idx, (full_name, status, is_vip, avatar_idx) in enumerate(CUSTOMERS, start=1):
            phone = demo_customer_phone(SALON_A_SLUG, idx)
            birth = _jalali_to_gregorian(j_today.year - 22 - (idx % 15), (idx % 12) + 1, min(28, (idx % 27) + 1))
            if idx in (7, 14, 21, 28):
                birth = _jalali_to_gregorian(j_today.year - 30, j_today.month, min(29, idx))
            c, _ = Customer.objects.update_or_create(
                salon=salon,
                phone=phone,
                defaults={
                    "full_name": full_name,
                    "is_deleted": False,
                    "status": getattr(Customer.Status, status.upper(), Customer.Status.ACTIVE),
                    "is_vip": is_vip,
                    "birth_date": birth,
                    "marketing_consent": idx % 4 != 0,
                },
            )
            if not c.avatar:
                c.avatar.save(
                    f"demo-customer-{idx}.png",
                    solid_avatar_file(f"cust-{idx}", f"#{avatar_idx*71 % 167:02x}{(avatar_idx * 43) % 167:02x}{(avatar_idx * 17) % 167:02x}"),
                    save=False,
                )
            c.save()
            c.tags.clear()
            if is_vip:
                c.tags.add(tags["VIP"])
            if status == "new":
                c.tags.add(tags["مشتری جدید"])
            if idx in (25, 26):
                c.tags.add(tags["بدهکار"])
            if idx in (27, 28):
                c.tags.add(tags["بیعانه‌دار"])
            if idx in (5, 14, 24):
                c.tags.add(tags["نیاز به پیگیری"])
            if idx <= len(NOTES):
                CustomerNote.objects.get_or_create(
                    salon=salon,
                    customer=c,
                    body=NOTES[idx - 1],
                )
            customers.append(c)
        self._say(f"customers: {len(customers)}")
        return customers

    def _seed_inventory(self, salon: Salon, actor: User) -> dict[str, InventoryItem]:
        cats = {
            "مراقبت مو": InventoryCategory.objects.get_or_create(salon=salon, name="مراقبت مو")[0],
            "آرایشی": InventoryCategory.objects.get_or_create(salon=salon, name="آرایشی")[0],
            "مصرفی": InventoryCategory.objects.get_or_create(salon=salon, name="مصرفی سالن")[0],
        }
        out: dict[str, InventoryItem] = {}
        sell_prices: dict[str, int] = {}
        for idx, (name, unit, qty, minimum, purchase, sell) in enumerate(PRODUCTS, start=1):
            if sell > 0:
                sell_prices[name] = sell
            cat = cats["مصرفی"]
            if "شامپو" in name or "کراتین" in name or "مژه" in name:
                cat = cats["مراقبت مو"]
            elif "ماسک" in name or "کرم" in name or "ژل" in name:
                cat = cats["آرایشی"]
            item = InventoryItem.scoped(salon).filter(name=name).first()
            if not item:
                item = create_inventory_item(
                    salon=salon,
                    name=name,
                    unit=unit,
                    minimum_quantity=Decimal(str(minimum)),
                    category=cat,
                    initial_quantity=Decimal(str(qty)),
                    note=DEMO_SALON_MARKER,
                )
            if item.purchase_price_toman != purchase:
                set_unit_cost(salon=salon, item_id=item.pk, unit_cost=purchase, actor=actor)
            item.refresh_from_db()
            out[name] = item
        self._say(f"inventory: {len(out)}")
        self._sell_prices = sell_prices
        return out

    def _seed_accounts(self, salon: Salon):
        today = timezone.localdate()
        for name, kind, opening in (
            ("[نمایشی] صندوق سالن", "cash", 1_500_000),
            ("[نمایشی] بانک پاسارگاد", "bank", 8_000_000),
        ):
            FinancialAccount.objects.get_or_create(
                salon=salon,
                name=name,
                defaults={"kind": kind, "opening_toman": opening, "opening_day": today},
            )

    def _seed_expenses(self, salon: Salon):
        today = timezone.localdate()
        for cat, amount, title in (
            (Expense.Category.RENT, 14_000_000, f"{DEMO_SALON_MARKER} اجاره آذر"),
            (Expense.Category.UTILITIES, 680_000, f"{DEMO_SALON_MARKER} برق و آب"),
            (Expense.Category.MARKETING, 2_400_000, f"{DEMO_SALON_MARKER} اینستاگرام"),
            (Expense.Category.SUPPLIES, 1_250_000, f"{DEMO_SALON_MARKER} مواد مصرفی هفته"),
        ):
            Expense.objects.get_or_create(
                salon=salon,
                category=cat,
                expense_date=today - timedelta(days=5 if cat == Expense.Category.RENT else 2),
                amount_toman=amount,
                defaults={"description": title},
            )
        due = today.replace(day=min(25, today.day))
        RecurringExpense.objects.get_or_create(
            salon=salon,
            title=f"{DEMO_SALON_MARKER} قبض اینترنت",
            defaults={
                "category": Expense.Category.UTILITIES,
                "amount_toman": 520_000,
                "day_of_month": 25,
                "next_due": due,
                "is_active": True,
            },
        )
        SalonDebt.objects.get_or_create(
            salon=salon,
            creditor_name="پخش آرایشی رز",
            defaults={
                "principal_toman": 6_500_000,
                "paid_toman": 2_000_000,
                "note": f"{DEMO_SALON_MARKER} خرید محصولات",
            },
        )

    def _seed_packages(self, salon: Salon) -> list[ServicePackage]:
        rows = []
        for name, price, sessions, validity in PACKAGE_DEFS:
            pkg, _ = ServicePackage.objects.get_or_create(
                salon=salon,
                name=name,
                defaults={
                    "price_toman": price,
                    "session_count": sessions,
                    "validity_days": validity,
                    "description": DEMO_SALON_MARKER,
                    "is_active": True,
                },
            )
            rows.append(pkg)
        return rows

    def _seed_loyalty_catalog(self, salon: Salon):
        for title, cost, desc in LOYALTY_REWARDS:
            LoyaltyReward.objects.get_or_create(
                salon=salon,
                title=title,
                defaults={"points_cost": cost, "description": f"{DEMO_SALON_MARKER} {desc}", "is_active": True},
            )

    def _status_for_offset(self, day_offset: int, seq: int) -> str:
        if day_offset < 0:
            return (
                Appointment.Status.COMPLETED
                if seq % 7 not in (5, 6)
                else (Appointment.Status.CANCELLED if seq % 2 else Appointment.Status.NO_SHOW)
            )
        if day_offset == 0:
            mapping = (
                Appointment.Status.CHECKED_IN,
                Appointment.Status.CONFIRMED,
                Appointment.Status.PENDING,
                Appointment.Status.CONFIRMED,
                Appointment.Status.CHECKED_IN,
            )
            return mapping[seq % len(mapping)]
        return Appointment.Status.CONFIRMED if seq % 3 else Appointment.Status.PENDING

    def _seed_appointments(
        self,
        salon: Salon,
        actor: User,
        customers: list[Customer],
        staff_map: dict[str, StaffProfile],
        services: list[Service],
    ) -> list[Appointment]:
        specialists = list(staff_map.values())
        spec_keys = list(staff_map.keys())
        tz = timezone.get_current_timezone()
        appts: list[Appointment] = []
        now = timezone.localtime()

        for i in range(120):
            day_offset = -85 + (i * 100) // 119
            target_day = now.date() + timedelta(days=day_offset)
            if target_day.weekday() == 4:  # جمعه میلادی ≈ often off — skip to شنبه
                target_day += timedelta(days=1)
            hour = 9 + (i % 9)
            minute = 15 if i % 2 else 0
            start = timezone.make_aware(datetime.combine(target_day, time(hour, minute)), tz)
            specialty = spec_keys[i % len(spec_keys)]
            staff = staff_map[specialty]
            service = next(s for s in services if specialty in (s.description or "") or s.category and s.category.name == specialty)
            customer = customers[i % len(customers)]
            status = self._status_for_offset(day_offset, i)

            exists = Appointment.scoped(salon).filter(customer=customer, start_at=start).exists()
            if exists:
                appts.append(Appointment.scoped(salon).get(customer=customer, start_at=start))
                continue

            if day_offset >= 0 and status in (
                Appointment.Status.PENDING,
                Appointment.Status.CONFIRMED,
                Appointment.Status.CHECKED_IN,
            ):
                try:
                    appt = create_appointment(
                        salon=salon,
                        customer=customer,
                        staff=staff,
                        service=service,
                        start=start,
                        actor=actor,
                        status=status,
                    )
                except SchedulingError:
                    end = start + timedelta(minutes=service.duration_minutes)
                    appt = Appointment.objects.create(
                        salon=salon,
                        customer=customer,
                        staff=staff,
                        service=service,
                        start_at=start,
                        end_at=end,
                        price_toman=service.price_toman,
                        status=status,
                    )
            else:
                end = start + timedelta(minutes=service.duration_minutes)
                completed_at = end if status == Appointment.Status.COMPLETED else None
                appt = Appointment.objects.create(
                    salon=salon,
                    customer=customer,
                    staff=staff,
                    service=service,
                    start_at=start,
                    end_at=end,
                    price_toman=service.price_toman,
                    status=status,
                    completed_at=completed_at,
                )
                if status == Appointment.Status.COMPLETED and completed_at:
                    complete_appointment(salon=salon, appointment_id=appt.pk)
                    appt.refresh_from_db()

            appts.append(appt)

        appts.extend(self._seed_today_appointments(salon, actor, customers, staff_map, services, appts))
        self._say(f"appointments: {len(appts)}")
        return appts

    def _seed_today_appointments(
        self,
        salon: Salon,
        actor: User,
        customers: list[Customer],
        staff_map: dict[str, StaffProfile],
        services: list[Service],
        existing: list[Appointment],
    ) -> list[Appointment]:
        """Guarantee a useful reception desk / calendar for local today."""
        today = timezone.localdate()
        tz = timezone.get_current_timezone()
        friday_demo = today.weekday() == 4
        specialists = list(staff_map.values())
        spec_keys = list(staff_map.keys())
        used = {(a.staff_id, a.start_at) for a in existing}
        extra: list[Appointment] = []
        today_count = sum(1 for a in existing if timezone.localtime(a.start_at).date() == today)
        target = max(0, 12 - today_count)
        for n in range(target):
            start = timezone.make_aware(datetime.combine(today, time(9 + n, 15 * (n % 2))), tz)
            staff = specialists[n % len(specialists)]
            specialty = spec_keys[n % len(spec_keys)]
            service = next(s for s in services if (s.category and s.category.name == specialty))
            customer = customers[(20 + n) % len(customers)]
            key = (staff.pk, start)
            if key in used:
                continue
            status = (
                Appointment.Status.CHECKED_IN
                if n % 4 == 0
                else (Appointment.Status.PENDING if n % 4 == 3 else Appointment.Status.CONFIRMED)
            )
            end = start + timedelta(minutes=service.duration_minutes)
            if friday_demo:
                appt, _ = Appointment.objects.get_or_create(
                    salon=salon,
                    customer=customer,
                    start_at=start,
                    defaults={
                        "staff": staff,
                        "service": service,
                        "end_at": end,
                        "price_toman": service.price_toman,
                        "status": status,
                    },
                )
            else:
                try:
                    appt = create_appointment(
                        salon=salon,
                        customer=customer,
                        staff=staff,
                        service=service,
                        start=start,
                        actor=actor,
                        status=status,
                    )
                except SchedulingError:
                    appt, _ = Appointment.objects.get_or_create(
                        salon=salon,
                        customer=customer,
                        start_at=start,
                        defaults={
                            "staff": staff,
                            "service": service,
                            "end_at": end,
                            "price_toman": service.price_toman,
                            "status": status,
                        },
                    )
            used.add(key)
            extra.append(appt)
        return extra

    def _seed_finance_flows(
        self,
        salon: Salon,
        actor: User,
        customers: list[Customer],
        appts: list[Appointment],
        items: dict[str, InventoryItem],
    ):
        completed = [a for a in appts if a.status == Appointment.Status.COMPLETED]
        for i, appt in enumerate(completed):
            if Payment.scoped(salon).filter(appointment=appt).exists():
                continue
            customer = appt.customer
            if i % 11 == 0:
                continue  # unpaid → customer debt
            if i % 9 == 0 and i < len(completed) - 1:
                deposit = int(appt.price_toman * 0.4)
                create_appointment_deposit(
                    salon=salon,
                    customer=customer,
                    appointment=appt,
                    amount_toman=deposit,
                    method=Payment.Method.CARD,
                )
                continue
            methods = [Payment.Method.CASH, Payment.Method.CARD, Payment.Method.TRANSFER]
            method = methods[i % 3]
            Payment.objects.create(
                salon=salon,
                customer=customer,
                appointment=appt,
                total_amount_toman=appt.price_toman,
                paid_amount_toman=appt.price_toman,
                discount_toman=50_000 if i % 13 == 0 else 0,
                method=method,
                status=Payment.Status.PAID,
            )
            refresh_customer_stats(customer)

        # multi-service checkout
        anchor = customers[1]
        day_appts = [a for a in completed if a.customer_id == anchor.pk][:2]
        if len(day_appts) >= 2:
            try:
                issue_invoice(
                    salon=salon,
                    customer_id=anchor.pk,
                    appointment_ids=[a.pk for a in day_appts],
                    request_key=_req_key("invoice-multi-1"),
                    discount=100_000,
                    amounts={"cash": 200_000, "card": day_appts[0].price_toman, "transfer": 0},
                    actor=actor,
                )
            except Exception:
                pass

        paid = Payment.scoped(salon).filter(status=Payment.Status.PAID, paid_amount_toman__gt=0).first()
        if paid:
            try:
                refund_payment(
                    salon=salon,
                    payment_id=paid.pk,
                    amount=min(150_000, int(paid.paid_amount_toman // 3)),
                    reason="درخواست مشتری — تغییر برنامه",
                    request_key=_req_key("refund-1"),
                    actor=actor,
                )
            except Exception:
                pass

        # product sales
        sellable = [(items[name], price) for name, price in getattr(self, "_sell_prices", {}).items() if name in items]
        for idx, cust in enumerate(customers[15:20]):
            if idx >= len(sellable):
                break
            it, unit_price = sellable[idx]
            try:
                sell_product(
                    salon=salon,
                    customer_id=cust.pk,
                    item_id=it.pk,
                    quantity=Decimal("1"),
                    unit_price=unit_price,
                    method=Payment.Method.CARD,
                    request_key=_req_key(f"sale-{cust.pk}-{it.pk}"),
                    actor=actor,
                )
            except Exception:
                pass

        # material consumption on completed hair/color appointments
        color_appt = next((a for a in completed if a.service and "رنگ" in a.service.name), None)
        consumable = items.get("شامپو ترمیمی کراتین") or next(iter(items.values()))
        if color_appt and consumable:
            try:
                consume_material(
                    salon=salon,
                    appointment_id=color_appt.pk,
                    item_id=consumable.pk,
                    quantity=Decimal("0.25"),
                    request_key=_req_key(f"material-{color_appt.pk}"),
                    actor=actor,
                )
            except Exception:
                pass

        yesterday = timezone.localdate() - timedelta(days=1)
        try:
            close_cash_day(
                salon=salon,
                day=yesterday,
                opening=500_000,
                other_in=0,
                cash_out=120_000,
                counted=800_000,
                note=DEMO_SALON_MARKER,
                actor=actor,
            )
        except Exception:
            pass

    def _seed_loyalty_members(self, salon: Salon, customers: list[Customer], packages: list[ServicePackage], actor: User):
        tier_points = [(0, 50), (1, 280), (2, 550), (3, 1100), (7, 220), (14, 480)]
        for cust, pts in tier_points:
            if cust < len(customers):
                ledger_add_points(
                    salon=salon,
                    customer=customers[cust],
                    points=pts,
                    reference=DEMO_SALON_MARKER,
                    note="امتیاز باشگاه",
                )
        reward = LoyaltyReward.scoped(salon).filter(is_active=True).order_by("points_cost").first()
        if reward and len(customers) > 3:
            cust = customers[3]
            from apps.loyalty.models import LoyaltyAccount

            account, _ = LoyaltyAccount.objects.get_or_create(salon=salon, customer=cust)
            try:
                redeem_reward(
                    salon=salon,
                    account_id=account.pk,
                    reward_id=reward.pk,
                    request_key=_req_key("redeem-1"),
                    actor=actor,
                )
            except Exception:
                try:
                    ledger_redeem_points(salon=salon, customer=cust, points=reward.points_cost, note="جایزه نمایشی")
                except Exception:
                    pass

        if len(packages) >= 1:
            buy_membership(
                salon=salon,
                customer_id=customers[2].pk,
                package_id=packages[0].pk,
                request_key=_req_key("membership-1"),
                actor=actor,
            )

        if len(customers) >= 6:
            try:
                register_referral(
                    salon=salon,
                    referrer_id=customers[4].pk,
                    referred_id=customers[5].pk,
                    actor=actor,
                )
            except Exception:
                pass

    def _seed_marketing(self, salon: Salon, actor: User, customers: list[Customer]):
        settings, _ = SalonSettings.objects.get_or_create(salon=salon)
        settings.sms_marketing_enabled = False
        settings.save(update_fields=["sms_marketing_enabled", "updated_at"])

        for idx, (title, segment, message) in enumerate(CAMPAIGNS):
            title = f"{DEMO_SALON_MARKER} {title}"
            camp, _ = Campaign.objects.get_or_create(
                salon=salon,
                title=title,
                defaults={
                    "segment": segment,
                    "message": message,
                    "status": Campaign.Status.DRAFT,
                    "request_key": _req_key(f"campaign-{idx}"),
                },
            )
            try:
                prepare_campaign(salon=salon, campaign_id=camp.pk, actor=actor)
            except Exception:
                pass

        for i, c in enumerate(customers[-5:]):
            FollowUp.objects.get_or_create(
                salon=salon,
                customer=c,
                reason=f"{DEMO_SALON_MARKER} پیگیری رضایت",
                defaults={"days_since_visit": 40 + i, "status": FollowUp.Status.OPEN},
            )

    def _seed_staff_payroll(self, salon: Salon, staff_map: dict[str, StaffProfile], actor: User):
        last_month = timezone.localdate().replace(day=1) - timedelta(days=1)
        month_start, _ = jalali_month_bounds(last_month)
        for spec in SPECIALISTS:
            mode, amount = spec["agreement"]
            if mode not in ("salary", "rent"):
                continue
            staff = staff_map[spec["specialty"]]
            try:
                period = open_staff_period(salon=salon, staff_id=staff.pk, month=month_start, actor=actor)
                pay_staff_period(
                    salon=salon,
                    period_id=period.pk,
                    kind="rent" if mode == "rent" else "advance",
                    amount=min(amount // 2, period.amount_toman),
                    request_key=_req_key(f"staff-pay-{staff.pk}"),
                    note=DEMO_SALON_MARKER,
                    actor=actor,
                )
            except Exception:
                pass

        commission_staff = staff_map[SPECIALISTS[0]["specialty"]]
        try:
            create_settlement(salon, commission_staff, 350_000, note=DEMO_SALON_MARKER)
        except Exception:
            pass

    def _seed_portfolio(self, salon: Salon):
        titles = ("هایلایت ملایم", "ناخن ژله‌ای", "میکاپ عروس کلاسیک", "شینیون مجلسی")
        for i, title in enumerate(titles, start=1):
            PortfolioItem.objects.get_or_create(
                salon=salon,
                title=title,
                defaults={"description": DEMO_SALON_MARKER, "is_published": True, "sort_order": i},
            )

    def _seed_waitlist(self, salon: Salon, customers: list[Customer], services: list[Service]):
        WaitlistEntry.objects.get_or_create(
            salon=salon,
            customer=customers[-1],
            service=services[0],
            defaults={"priority": 7, "time_note": "صبح", "status": WaitlistEntry.Status.OPEN},
        )

    def _verify(self, salon: Salon, customers, services, appts) -> str:
        from apps.commissions.models import CommissionEntry

        c_appt = len(appts)
        c_comm = CommissionEntry.scoped(salon).count()
        c_pay = Payment.scoped(salon).filter(customer__phone__startswith=demo_customer_phone(SALON_A_SLUG, 1)[:10]).count()
        today = Appointment.scoped(salon).filter(start_at__date=timezone.localdate()).count()
        return (
            f"appts={c_appt}, today={today}, services={len(services)}, customers={len(customers)}, "
            f"payments~demo={c_pay}, commissions={c_comm}"
        )
