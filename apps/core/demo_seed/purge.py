"""Remove seeded demo and mock data, optionally destroying demo salons entirely."""

from __future__ import annotations

from django.apps import apps
from django.db import transaction
from django.db.models import ProtectedError, Q

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.core.demo_seed.engine import (
    DEMO_MARKER,
    DEMO_SALON_SLUGS,
    DEMO_USER_PHONES,
    OWNER_PHONES,
    DemoSeedEngine,
)
from apps.core.demo_seed.finance_timeline import TIMELINE_NOTE
from apps.core.demo_seed.salon_dataset import DEMO_SALON_MARKER, SPECIALISTS, specialist_phone
from apps.core.demo_seed.salon_reset import reset_demo_salon
from apps.core.tenant import TenantModelMixin
from apps.expenses.models import Expense
from apps.salons.models import Salon, SalonInvitation, SalonMembership


def _iter_salon_scoped_models():
    seen = set()
    for model in apps.get_models():
        if model._meta.abstract or model in seen:
            continue
        if issubclass(model, TenantModelMixin):
            seen.add(model)
            yield model
            continue
        if any(f.name == "salon" and getattr(f.remote_field, "model", None) is Salon for f in model._meta.fields):
            seen.add(model)
            yield model


def _flush_salon_scoped_data(salon: Salon) -> dict[str, int]:
    deleted: dict[str, int] = {}
    models = list(_iter_salon_scoped_models())
    for _ in range(64):
        made_progress = False
        for model in models:
            label = model._meta.label_lower
            qs = model.objects.filter(salon=salon)
            if not qs.exists():
                continue
            try:
                count, _ = qs.delete()
            except ProtectedError:
                continue
            if count:
                deleted[label] = deleted.get(label, 0) + count
                made_progress = True
        if not made_progress:
            break
    AuditLog.objects.filter(salon=salon).update(salon=None)
    return deleted


def _destroy_demo_salon(salon: Salon) -> dict[str, object]:
    SalonInvitation.objects.filter(salon=salon).delete()
    memberships = SalonMembership.objects.filter(salon=salon).count()
    salon_id = salon.pk
    salon_slug = salon.slug
    salon.delete()
    return {"destroyed": True, "slug": salon_slug, "memberships_removed": memberships, "salon_id": str(salon_id)}


def demo_user_phones() -> set[str]:
    phones = set(OWNER_PHONES.values()) | set(DEMO_USER_PHONES.values())
    phones.update(specialist_phone(i) for i in range(1, len(SPECIALISTS) + 1))
    phones.update(f"+989121000{i:03d}" for i in range(100, 110))
    return phones


def _purge_orphan_demo_users() -> int:
    removed = 0
    for phone in demo_user_phones():
        user = User.objects.filter(phone=phone).first()
        if not user:
            continue
        if SalonMembership.objects.filter(user=user).exists():
            continue
        user.delete()
        removed += 1
    return removed


@transaction.atomic
def purge_stray_demo_rows() -> dict[str, int]:
    """Demo markers that may exist outside the canonical demo salons."""
    expense_q = Q(description__contains=TIMELINE_NOTE) | Q(description__startswith=DEMO_SALON_MARKER) | Q(
        description__startswith=DEMO_MARKER
    )
    return {"expenses_global": Expense.objects.filter(expense_q).delete()[0]}


@transaction.atomic
def purge_all_demo_data(*, stdout=None, destroy_salons: bool = True) -> dict[str, object]:
    engine = DemoSeedEngine(dry_run=False, stdout=stdout)
    summary: dict[str, object] = {"salons": {}, "stray": purge_stray_demo_rows(), "destroy_salons": destroy_salons}

    for slug in DEMO_SALON_SLUGS:
        salon = Salon.objects.filter(slug=slug).first()
        if not salon:
            summary["salons"][slug] = "missing"
            continue
        row: dict[str, object] = {}
        if slug == "demo-salon-a":
            reset_demo_salon(salon)
            row["reset_demo_salon"] = True
        engine.reset_demo([slug])
        row["reset_demo_engine"] = True
        row["flushed"] = _flush_salon_scoped_data(salon)
        if destroy_salons:
            row.update(_destroy_demo_salon(salon))
        summary["salons"][slug] = row

    summary["demo_users_removed"] = _purge_orphan_demo_users()
    return summary