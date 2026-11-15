"""Idempotent demo data for BeautyOS showcase — fixed salon slugs + hidden demo_seed_v2 markers."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Iterable

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import User
from apps.appointments.models import Appointment
from apps.appointments.services.scheduling import SchedulingError, create_appointment
from apps.commissions.models import CommissionEntry, CommissionRule, CommissionSettlement
from apps.customers.models import Customer, CustomerTag
from apps.customers.services import refresh_customer_stats
from apps.expenses.models import Expense
from apps.finance.models import Payment
from apps.inventory.models import InventoryItem, StockMovement
from apps.loyalty.models import LoyaltyAccount, LoyaltyTransaction, ledger_add_points
from apps.packages.models import CustomerPackage, PackageSessionUse, ServicePackage
from apps.portfolio.models import PortfolioItem
from apps.retention.models import FollowUp
from apps.salons.business_catalog import presets_for
from apps.salons.models import Salon, SalonInvitation, SalonMembership, SalonSettings
from apps.salons.themes import BUSINESS_TYPE_DEFAULTS
from apps.services.models import Service, ServiceCategory
from apps.staff.models import StaffProfile, StaffWorkHours
from apps.waitlist.models import WaitlistEntry

from apps.core.demo_seed.labels import DEMO_LEGACY_PREFIX, scrub_salon_demo_labels
from apps.core.demo_seed.personas import (
    BARBER_CUSTOMERS,
    BEAUTY_CUSTOMERS,
    FOLLOWUP_REASONS,
    PORTFOLIO_TITLES_BARBER,
    PORTFOLIO_TITLES_BEAUTY,
)
DEMO_MARKER = "demo_seed_v2"
DEMO_INVENTORY_NAMES = ("شامپو حرفه‌ای", "رنگ مو", "کرم پوست")
DEMO_SALON_SLUGS = ("demo-salon-a", "demo-barber-b")

SALON_A_SLUG = "demo-salon-a"
SALON_B_SLUG = "demo-barber-b"

OWNER_PHONES = {
    SALON_A_SLUG: "+989121000001",
    SALON_B_SLUG: "+989121000002",
}

DEMO_USER_PHONES = {
    "reception_a": "+989121000101",
    "manager_a": "+989121000103",
    "specialist_a2": "+989121000102",
    "reception_b": "+989121000201",
    "specialist_b2": "+989121000202",
}


def demo_customer_name(salon_slug: str, index: int) -> str:
    pool = BEAUTY_CUSTOMERS if salon_slug == SALON_A_SLUG else BARBER_CUSTOMERS
    return pool[(index - 1) % len(pool)]


def demo_customer_phone(salon_slug: str, index: int) -> str:
    base = 3100000 if salon_slug == SALON_A_SLUG else 3200000
    return f"+98912{base + index:07d}"


def demo_customer_phone_prefix(salon_slug: str) -> str:
    """Shared MSISDN prefix for seeded demo customers (excludes owner/staff phones)."""
    digit = "31" if salon_slug == SALON_A_SLUG else "32"
    return f"+98912{digit}"


def demo_customers_for_salon(salon):
    from apps.customers.models import Customer

    prefix = demo_customer_phone_prefix(salon.slug)
    return Customer.scoped(salon).filter(
        Q(phone__startswith=prefix) | Q(full_name__startswith=DEMO_LEGACY_PREFIX),
    )


@dataclass
class SeedPlan:
    actions: list[str] = field(default_factory=list)

    def log(self, msg: str):
        self.actions.append(msg)


class DemoSeedEngine:
    def __init__(self, *, dry_run: bool = False, stdout=None):
        self.dry_run = dry_run
        self.stdout = stdout
        self.plan = SeedPlan()
        random.seed(42)

    def _say(self, msg: str):
        if self.stdout:
            self.stdout.write(msg)
        self.plan.log(msg)

    def reset_demo(self, salon_slugs: Iterable[str] | None = None):
        slugs = list(salon_slugs or DEMO_SALON_SLUGS)
        for slug in slugs:
            salon = Salon.objects.filter(slug=slug).first()
            if not salon:
                continue
            self._say(f"reset: {slug}")
            if self.dry_run:
                continue
            self._reset_salon(salon)

    @transaction.atomic
    def _reset_salon(self, salon: Salon):
        demo_customers = demo_customers_for_salon(salon)
        cids = list(demo_customers.values_list("pk", flat=True))

        CommissionEntry.scoped(salon).delete()
        CommissionSettlement.scoped(salon).delete()
        CommissionRule.scoped(salon).all().delete()
        PackageSessionUse.scoped(salon).filter(customer_package__customer_id__in=cids).delete()
        CustomerPackage.scoped(salon).filter(customer_id__in=cids).delete()
        ServicePackage.scoped(salon).filter(description__startswith=DEMO_MARKER).delete()
        Payment.scoped(salon).filter(customer_id__in=cids).delete()
        WaitlistEntry.scoped(salon).filter(customer_id__in=cids).delete()
        FollowUp.scoped(salon).filter(customer_id__in=cids).delete()
        LoyaltyTransaction.scoped(salon).filter(account__customer_id__in=cids).delete()
        LoyaltyAccount.scoped(salon).filter(customer_id__in=cids).delete()
        StockMovement.scoped(salon).all().delete()
        InventoryItem.scoped(salon).filter(name__in=DEMO_INVENTORY_NAMES).delete()
        Expense.scoped(salon).all().delete()
        Appointment.scoped(salon).filter(customer_id__in=cids).delete()
        PortfolioItem.scoped(salon).filter(title__contains=DEMO_LEGACY_PREFIX).delete()
        demo_customers.update(is_deleted=True)
        SalonInvitation.objects.filter(salon=salon, phone__startswith="+989121000").delete()

    def run(
        self,
        scenario: str = "full",
        salon_slugs: Iterable[str] | None = None,
        reset_first: bool = False,
    ):
        slugs = list(salon_slugs or DEMO_SALON_SLUGS)
        if reset_first or scenario == "empty":
            self.reset_demo(slugs)
            if scenario == "empty":
                self._say("empty scenario: demo transactional data cleared")
                return self.plan

        if not self.dry_run and scenario != "empty":
            for slug in slugs:
                salon = Salon.objects.filter(slug=slug).first()
                if salon:
                    n = scrub_salon_demo_labels(salon)
                    if n:
                        self._say(f"scrubbed {n} legacy [دمو] labels in {slug}")

        if scenario == "minimal":
            for slug in slugs:
                self._seed_minimal(slug)
        elif scenario == "busy-day":
            for slug in slugs:
                self._ensure_salon(slug)
            if SALON_A_SLUG in slugs:
                self._seed_busy_day(SALON_A_SLUG)
        elif scenario == "full":
            for slug in slugs:
                self._seed_full(slug)
        else:
            raise ValueError(f"Unknown scenario: {scenario}")
        return self.plan

    def _ensure_salon(self, slug: str) -> tuple[User, Salon]:
        configs = {
            SALON_A_SLUG: {
                "name": "آتلیه لاله",
                "business_type": Salon.BusinessType.BEAUTY_WOMEN,
                "public_theme": Salon.PublicTheme.ELEGANT_BEAUTY,
                "tagline": "زیبایی و مراقبت با جزئیات ظریف",
                "owner_phone": OWNER_PHONES[SALON_A_SLUG],
                "owner_name": "مریم کاشکولی",
                "city": "تهران",
            },
            SALON_B_SLUG: {
                "name": "آرایشگاه گلستان",
                "business_type": Salon.BusinessType.BARBER_MEN,
                "public_theme": Salon.PublicTheme.MODERN_BARBER,
                "tagline": "استایل مردانه مدرن و دقیق",
                "owner_phone": OWNER_PHONES[SALON_B_SLUG],
                "owner_name": "حسین محمدی",
                "city": "تهران",
            },
        }
        cfg = configs[slug]
        owner, _ = User.objects.get_or_create(phone=cfg["owner_phone"], defaults={"full_name": cfg["owner_name"]})
        if owner.full_name != cfg["owner_name"]:
            owner.full_name = cfg["owner_name"]
            owner.save(update_fields=["full_name", "updated_at"])
        if self.dry_run:
            self._say(f"salon ready (dry): {slug}")
            return owner, Salon(slug=slug, name=cfg["name"])
        salon, _ = Salon.objects.get_or_create(
            slug=slug,
            defaults={
                "name": cfg["name"],
                "city": cfg["city"],
                "tagline": cfg["tagline"],
                "description": f"{DEMO_MARKER} {cfg['tagline']}",
                "public_theme": cfg["public_theme"],
                "business_type": cfg["business_type"],
            },
        )
        for field, val in [
            ("name", cfg["name"]),
            ("business_type", cfg["business_type"]),
            ("public_theme", cfg["public_theme"]),
            ("tagline", cfg["tagline"]),
        ]:
            if getattr(salon, field) != val:
                setattr(salon, field, val)
        if salon.description.startswith(DEMO_MARKER):
            salon.description = cfg["tagline"]
        salon.save()

        settings, _ = SalonSettings.objects.get_or_create(salon=salon)
        dash, _ = BUSINESS_TYPE_DEFAULTS.get(cfg["business_type"], BUSINESS_TYPE_DEFAULTS[Salon.BusinessType.COMBINED])
        if settings.dashboard_theme != dash:
            settings.dashboard_theme = dash
        if not settings.onboarding_completed_at:
            settings.onboarding_completed_at = timezone.now()
        settings.save()

        SalonMembership.objects.get_or_create(user=owner, salon=salon, defaults={"role": SalonMembership.Role.OWNER})
        self._say(f"salon ready: {slug}")
        return owner, salon

    def _seed_minimal(self, slug: str):
        owner, salon = self._ensure_salon(slug)
        if self.dry_run:
            self._say(f"minimal plan for {slug}")
            return
        cat_label = "خدمات زیبایی" if salon.business_type == Salon.BusinessType.BEAUTY_WOMEN else "خدمات آرایشگری"
        cat, _ = ServiceCategory.objects.get_or_create(salon=salon, name=cat_label, defaults={"sort_order": 1})
        presets = presets_for(salon.business_type)[:2]
        services = []
        for p in presets:
            svc, _ = Service.objects.get_or_create(
                salon=salon,
                name=p["name"],
                defaults={
                    "category": cat,
                    "price_toman": p["price_toman"],
                    "duration_minutes": p["duration_minutes"],
                    "description": f"رزرو آنلاین · حدود {p['duration_minutes']} دقیقه",
                    "is_public": True,
                },
            )
            services.append(svc)
        staff = self._ensure_primary_staff(salon, owner, services)
        for i in (1, 2):
            self._upsert_customer(salon, i)
        c = Customer.scoped(salon).filter(full_name=demo_customer_name(salon.slug, 1)).first()
        start = self._next_open_slot(staff, days_ahead=2)
        if c and start:
            self._ensure_appointment(salon, owner, c, staff, services[0], start)

    def _seed_full(self, slug: str):
        owner, salon = self._ensure_salon(slug)
        if self.dry_run:
            self._say(f"full plan for {slug}")
            return
        self._seed_team(slug, salon, owner)
        services = self._seed_services(salon)
        staff_profiles = list(StaffProfile.scoped(salon).filter(is_active=True))
        primary = staff_profiles[0] if staff_profiles else self._ensure_primary_staff(salon, owner, services)
        customers = [self._upsert_customer(salon, i) for i in range(1, 13)]

        for i, c in enumerate(customers[:6], start=1):
            past = timezone.localtime() - timedelta(days=10 + i)
            past = past.replace(hour=10 + i, minute=0, second=0, microsecond=0)
            self._ensure_past_completed(salon, owner, c, primary, services[i % len(services)], past)

        today_base = timezone.localtime().replace(hour=9, minute=0, second=0, microsecond=0)
        for i, c in enumerate(customers[6:10]):
            start = today_base + timedelta(hours=i * 2 + 1)
            st = staff_profiles[i % len(staff_profiles)] if staff_profiles else primary
            status = Appointment.Status.CONFIRMED if i % 2 == 0 else Appointment.Status.PENDING
            self._ensure_appointment(salon, owner, c, st, services[i % len(services)], start, status=status)

        for i, c in enumerate(customers[10:12], start=1):
            start = self._next_open_slot(primary, days_ahead=3 + i)
            if start:
                self._ensure_appointment(salon, owner, c, primary, services[0], start)

        CommissionRule.objects.get_or_create(
            salon=salon,
            name="پورسانت خدمات ۴۰٪",
            defaults={"percent": 40, "is_active": True},
        )

        expense_blurbs = {
            Expense.Category.SUPPLIES: "خرید مواد مصرفی و شامپو حرفه‌ای",
            Expense.Category.RENT: "اجاره واحد — آبان",
            Expense.Category.MARKETING: "تبلیغات اینستاگرام و استوری",
        }
        for cat, amount in [
            (Expense.Category.SUPPLIES, 850_000),
            (Expense.Category.RENT, 12_000_000),
            (Expense.Category.MARKETING, 2_500_000),
        ]:
            Expense.objects.get_or_create(
                salon=salon,
                category=cat,
                expense_date=timezone.localdate(),
                amount_toman=amount,
                defaults={"description": expense_blurbs[cat]},
            )

        pkg, _ = ServicePackage.objects.get_or_create(
            salon=salon,
            name="پکیج مراقبت مو — ۵ جلسه",
            defaults={
                "price_toman": 4_500_000,
                "session_count": 5,
                "validity_days": 180,
                "description": DEMO_MARKER,
            },
        )
        vip = customers[0]
        if not CustomerPackage.scoped(salon).filter(customer=vip, package=pkg).exists():
            from datetime import timedelta as td

            CustomerPackage.objects.create(
                salon=salon,
                customer=vip,
                package=pkg,
                sessions_total=pkg.session_count,
                price_paid_toman=pkg.price_toman,
                expires_at=timezone.now() + td(days=pkg.validity_days),
            )

        for name, qty in [("شامپو حرفه‌ای", 24), ("رنگ مو", 8), ("کرم پوست", 5)]:
            item, _ = InventoryItem.objects.get_or_create(
                salon=salon,
                name=name,
                defaults={"quantity": qty, "minimum_quantity": 3, "unit": "عدد"},
            )
            if item.quantity < qty:
                item.quantity = qty
                item.save(update_fields=["quantity", "updated_at"])

        for c in customers[:3]:
            if not LoyaltyAccount.objects.filter(salon=salon, customer=c).exists():
                ledger_add_points(salon=salon, customer=c, points=120, reference=DEMO_MARKER, note="امتیاز خوش‌آمدگویی")

        if len(customers) >= 2:
            WaitlistEntry.objects.get_or_create(
                salon=salon,
                customer=customers[-1],
                service=services[0],
                defaults={"priority": 8, "time_note": "عصر", "status": WaitlistEntry.Status.OPEN},
            )

        for i, c in enumerate(customers[-3:]):
            reason = FOLLOWUP_REASONS[i % len(FOLLOWUP_REASONS)]
            FollowUp.objects.get_or_create(
                salon=salon,
                customer=c,
                reason=reason,
                defaults={"days_since_visit": 35 + i, "status": FollowUp.Status.OPEN},
            )

        portfolio_titles = PORTFOLIO_TITLES_BEAUTY if salon.business_type == Salon.BusinessType.BEAUTY_WOMEN else PORTFOLIO_TITLES_BARBER
        for i, title in enumerate(portfolio_titles, start=1):
            PortfolioItem.objects.get_or_create(
                salon=salon,
                title=title,
                defaults={"description": "نمونه‌کار نمایشی", "is_published": True, "sort_order": i},
            )

        self._say(f"full seed done: {slug}")

    def _seed_busy_day(self, slug: str):
        if self.dry_run:
            self._say(f"busy-day plan for {slug}")
            return
        owner, salon = self._ensure_salon(slug)
        services = self._seed_services(salon)
        staff = self._ensure_primary_staff(salon, owner, services)
        customers = [self._upsert_customer(salon, i) for i in range(1, 16)]
        start = timezone.localtime().replace(hour=9, minute=0, second=0, microsecond=0)
        for i in range(15):
            c = customers[i % len(customers)]
            slot = start + timedelta(minutes=30 * i)
            self._ensure_appointment(
                salon,
                owner,
                c,
                staff,
                services[i % len(services)],
                slot,
                status=Appointment.Status.CONFIRMED if i % 3 else Appointment.Status.CHECKED_IN,
            )
        self._say(f"busy-day: 15 appointments today for {slug}")

    def _seed_team(self, slug: str, salon: Salon, owner: User):
        if slug == SALON_A_SLUG:
            extras = [
                (DEMO_USER_PHONES["reception_a"], "سارا نظری", SalonMembership.Role.RECEPTIONIST, None),
                (DEMO_USER_PHONES["manager_a"], "الهام موسوی", SalonMembership.Role.MANAGER, None),
                (DEMO_USER_PHONES["specialist_a2"], "شیما حیدری", SalonMembership.Role.SPECIALIST, "متخصص رنگ و لایت"),
            ]
        else:
            extras = [
                (DEMO_USER_PHONES["reception_b"], "امیر توکلی", SalonMembership.Role.RECEPTIONIST, None),
                (DEMO_USER_PHONES["specialist_b2"], "پارسا جعفری", SalonMembership.Role.SPECIALIST, "آرایشگر فید و ریش"),
            ]
        for phone, name, role, title in extras:
            user, _ = User.objects.get_or_create(phone=phone, defaults={"full_name": name})
            if user.full_name != name:
                user.full_name = name
                user.save(update_fields=["full_name", "updated_at"])
            mem, _ = SalonMembership.objects.get_or_create(user=user, salon=salon, defaults={"role": role})
            if mem.role != role:
                mem.role = role
                mem.save(update_fields=["role", "updated_at"])
            if role == SalonMembership.Role.SPECIALIST:
                StaffProfile.objects.get_or_create(
                    salon=salon,
                    membership=mem,
                    defaults={"display_name": name, "title": title or "", "is_bookable": True},
                )

    def _seed_services(self, salon: Salon) -> list[Service]:
        cat_label = "خدمات زیبایی" if salon.business_type == Salon.BusinessType.BEAUTY_WOMEN else "خدمات آرایشگری"
        cat, _ = ServiceCategory.objects.get_or_create(
            salon=salon, name=cat_label, defaults={"sort_order": 1}
        )
        services = []
        for p in presets_for(salon.business_type)[:6]:
            svc, _ = Service.objects.get_or_create(
                salon=salon,
                name=p["name"],
                defaults={
                    "category": cat,
                    "price_toman": p["price_toman"],
                    "duration_minutes": p["duration_minutes"],
                    "description": f"رزرو آنلاین · حدود {p['duration_minutes']} دقیقه",
                    "is_public": True,
                },
            )
            services.append(svc)
        return services

    def _ensure_primary_staff(self, salon: Salon, owner: User, services: list[Service]) -> StaffProfile:
        mem = SalonMembership.objects.get(user=owner, salon=salon)
        staff, _ = StaffProfile.objects.get_or_create(
            salon=salon,
            membership=mem,
            defaults={
                "display_name": owner.full_name,
                "title": "متخصص ارشد",
                "is_bookable": True,
            },
        )
        staff.services.set(services)
        for weekday in range(6):
            StaffWorkHours.objects.get_or_create(
                salon=salon,
                staff=staff,
                weekday=weekday,
                defaults={"start_time": time(9, 0), "end_time": time(21, 0)},
            )
        StaffWorkHours.objects.get_or_create(
            salon=salon,
            staff=staff,
            weekday=6,
            defaults={"is_closed": True, "start_time": time(0, 0), "end_time": time(0, 0)},
        )
        return staff

    def _upsert_customer(self, salon: Salon, index: int) -> Customer:
        phone = demo_customer_phone(salon.slug, index)
        name = demo_customer_name(salon.slug, index)
        c, created = Customer.objects.get_or_create(
            salon=salon,
            phone=phone,
            defaults={
                "full_name": name,
                "is_vip": index == 1,
                "status": Customer.Status.ACTIVE if index > 2 else Customer.Status.NEW,
                "email": f"demo{index}@example.local",
            },
        )
        updated_fields = []
        if c.full_name != name:
            c.full_name = name
            updated_fields.append("full_name")
        if c.is_deleted:
            c.is_deleted = False
            updated_fields.append("is_deleted")
        demo_email = f"demo{index}@example.local"
        if c.email != demo_email:
            c.email = demo_email
            updated_fields.append("email")
        if updated_fields:
            updated_fields.append("updated_at")
            c.save(update_fields=updated_fields)
        if index == 1:
            vip, _ = CustomerTag.objects.get_or_create(salon=salon, name="VIP", defaults={"is_system": True})
            c.tags.add(vip)
        return c

    def _next_open_slot(self, staff: StaffProfile, *, days_ahead: int) -> datetime | None:
        start = timezone.localtime() + timedelta(days=days_ahead)
        return start.replace(hour=14, minute=0, second=0, microsecond=0)

    def _ensure_appointment(
        self,
        salon,
        actor,
        customer,
        staff,
        service,
        start,
        status=Appointment.Status.CONFIRMED,
    ):
        end = start + timedelta(minutes=service.duration_minutes)
        exists = Appointment.scoped(salon).filter(customer=customer, start_at=start).exists()
        if exists:
            return
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
            if appt.status != status:
                appt.status = status
                appt.save(update_fields=["status", "updated_at"])
        except SchedulingError:
            Appointment.objects.create(
                salon=salon,
                customer=customer,
                staff=staff,
                service=service,
                start_at=start,
                end_at=end,
                status=status,
                price_toman=service.price_toman,
            )

    def _ensure_past_completed(self, salon, actor, customer, staff, service, start):
        end = start + timedelta(minutes=service.duration_minutes)
        appt, created = Appointment.objects.get_or_create(
            salon=salon,
            customer=customer,
            start_at=start,
            defaults={
                "staff": staff,
                "service": service,
                "end_at": end,
                "status": Appointment.Status.COMPLETED,
                "price_toman": service.price_toman,
                "completed_at": end,
            },
        )
        if created or not Payment.scoped(salon).filter(appointment=appt).exists():
            Payment.objects.get_or_create(
                salon=salon,
                customer=customer,
                appointment=appt,
                defaults={
                    "total_amount_toman": appt.price_toman,
                    "paid_amount_toman": appt.price_toman,
                    "status": Payment.Status.PAID,
                },
            )
            refresh_customer_stats(customer)
