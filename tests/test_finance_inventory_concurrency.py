"""Concurrent debt payment and inventory withdrawal — requires PostgreSQL."""

from __future__ import annotations

import threading
from decimal import Decimal
from urllib.parse import urlencode

import pytest
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connections
from django.db.models import Sum
from django.test import Client
from django.urls import reverse

from apps.finance.models import SalonDebt, SalonDebtPayment
from apps.finance.services import audit_debt_payment_consistency, record_salon_debt_payment
from apps.inventory.models import InventoryItem, StockMovement
from apps.inventory.services import apply_movement, audit_inventory_consistency


def _is_postgresql() -> bool:
    return "postgresql" in settings.DATABASES["default"]["ENGINE"]


requires_postgresql = pytest.mark.skipif(
    not _is_postgresql(),
    reason="PostgreSQL required (set DATABASE_URL in .env)",
)

OVER_BALANCE_MSG = "بیش از مانده بدهی"
INSUFFICIENT_STOCK_MSG = "موجودی کافی نیست"


def _auth_client(user, salon) -> Client:
    client = Client()
    client.force_login(user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()
    return client


def _concurrent_barrier_call(fn_a, fn_b):
    barrier = threading.Barrier(2)
    results: list = [None, None]

    def worker(fn, idx):
        connections.close_all()
        try:
            barrier.wait(timeout=15)
            results[idx] = fn()
        except Exception as exc:
            results[idx] = exc
        finally:
            connections.close_all()

    threads = [
        threading.Thread(target=worker, args=(fn_a, 0)),
        threading.Thread(target=worker, args=(fn_b, 1)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    return results


def _concurrent_http_post(user, salon, url_a, fields_a, url_b, fields_b):
    barrier = threading.Barrier(2)
    results: list[dict] = [{}, {}]

    def worker(url, fields, idx):
        connections.close_all()
        try:
            client = _auth_client(user, salon)
            barrier.wait(timeout=15)
            resp = client.post(url, fields)
            results[idx] = {"status": resp.status_code, "body": resp.content.decode()}
        except Exception as exc:
            results[idx] = {"error": repr(exc)}
        finally:
            connections.close_all()

    threads = [
        threading.Thread(target=worker, args=(url_a, fields_a, 0)),
        threading.Thread(target=worker, args=(url_b, fields_b, 1)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    return results


@pytest.mark.django_db
def test_record_debt_payment_rejects_amount_above_balance(salon):
    debt = SalonDebt.objects.create(salon=salon, creditor_name="cap", principal_toman=100, paid_toman=0)
    record_salon_debt_payment(salon=salon, debt_id=debt.pk, amount_toman=80)
    debt.refresh_from_db()
    with pytest.raises(ValidationError, match=OVER_BALANCE_MSG):
        record_salon_debt_payment(salon=salon, debt_id=debt.pk, amount_toman=80)
    assert SalonDebtPayment.objects.filter(debt=debt).count() == 1
    assert debt.paid_toman == 80


@pytest.mark.django_db
def test_apply_movement_rejects_above_stock(salon):
    item = InventoryItem.objects.create(
        salon=salon,
        name="cap",
        unit=InventoryItem.Unit.PIECE,
        quantity=Decimal("10"),
        minimum_quantity=Decimal("0"),
    )
    apply_movement(salon=salon, item=item, kind=StockMovement.Kind.OUT, quantity=Decimal("8"))
    item.refresh_from_db()
    with pytest.raises(ValidationError, match=INSUFFICIENT_STOCK_MSG):
        apply_movement(salon=salon, item=item, kind=StockMovement.Kind.OUT, quantity=Decimal("8"))
    assert item.quantity == Decimal("2")
    assert StockMovement.objects.filter(item=item, kind=StockMovement.Kind.OUT).count() == 1


@pytest.mark.django_db(transaction=True)
@requires_postgresql
def test_concurrent_debt_payments_one_winner(salon, owner_membership):
    debt = SalonDebt.objects.create(
        salon=salon,
        creditor_name="تست هم‌زمان",
        principal_toman=100,
        paid_toman=0,
    )

    def pay():
        return record_salon_debt_payment(salon=salon, debt_id=debt.pk, amount_toman=80)

    results = _concurrent_barrier_call(pay, pay)

    ok = sum(1 for r in results if not isinstance(r, Exception))
    rejected = sum(1 for r in results if isinstance(r, ValidationError))
    assert ok == 1, results
    assert rejected == 1, results

    debt.refresh_from_db()
    assert SalonDebtPayment.objects.filter(debt=debt).count() == 1
    assert SalonDebtPayment.objects.filter(debt=debt).aggregate(t=Sum("amount_toman"))["t"] == 80
    assert debt.paid_toman == 80
    assert debt.balance_toman == 20
    assert debt.is_closed is False

    exc = next(r for r in results if isinstance(r, ValidationError))
    assert "مانده فعلی" in str(exc)


@pytest.mark.django_db(transaction=True)
@requires_postgresql
def test_concurrent_debt_payments_via_http(salon, owner_membership):
    debt = SalonDebt.objects.create(
        salon=salon,
        creditor_name="HTTP",
        principal_toman=100,
        paid_toman=0,
    )
    url = reverse("finance:overview") + "?" + urlencode({"tab": "debts"})
    fields = {"action": "pay_debt", "debt_id": debt.pk, "amount_toman": 80}
    results = _concurrent_http_post(owner_membership.user, salon, url, fields, url, fields)

    assert not results[0].get("error") and not results[1].get("error")
    redirects = sum(1 for r in results if r["status"] == 302)
    assert redirects == 1
    debt.refresh_from_db()
    assert SalonDebtPayment.objects.filter(debt=debt).count() == 1
    assert debt.paid_toman == 80
    assert debt.balance_toman == 20


@pytest.mark.django_db
@requires_postgresql
def test_debt_payment_exact_balance_closes(salon):
    debt = SalonDebt.objects.create(salon=salon, creditor_name="exact", principal_toman=100)
    record_salon_debt_payment(salon=salon, debt_id=debt.pk, amount_toman=100)
    debt.refresh_from_db()
    assert debt.paid_toman == 100
    assert debt.balance_toman == 0
    assert debt.is_closed is True
    assert SalonDebtPayment.objects.filter(debt=debt).count() == 1


@pytest.mark.django_db(transaction=True)
@requires_postgresql
def test_concurrent_stock_out_one_winner(salon):
    item = InventoryItem.objects.create(
        salon=salon,
        name="هم‌زمان",
        unit=InventoryItem.Unit.PIECE,
        quantity=Decimal("10"),
        minimum_quantity=Decimal("0"),
    )

    def take():
        return apply_movement(
            salon=salon,
            item=item,
            kind=StockMovement.Kind.OUT,
            quantity=Decimal("8"),
        )

    results = _concurrent_barrier_call(take, take)
    ok = sum(1 for r in results if not isinstance(r, Exception))
    rejected = sum(1 for r in results if isinstance(r, ValidationError))
    assert ok == 1
    assert rejected == 1

    item.refresh_from_db()
    assert item.quantity == Decimal("2")
    assert StockMovement.objects.filter(item=item, kind=StockMovement.Kind.OUT).count() == 1
    assert StockMovement.objects.filter(item=item, kind=StockMovement.Kind.OUT).aggregate(t=Sum("quantity"))["t"] == Decimal("8")


@pytest.mark.django_db(transaction=True)
@requires_postgresql
def test_concurrent_stock_out_via_http(salon, owner_membership):
    item = InventoryItem.objects.create(
        salon=salon,
        name="HTTP-Stock",
        unit=InventoryItem.Unit.PIECE,
        quantity=Decimal("10"),
        minimum_quantity=Decimal("0"),
    )
    url = reverse("inventory:stock_out", kwargs={"pk": item.pk})
    fields = {"quantity": "8", "note": ""}
    results = _concurrent_http_post(owner_membership.user, salon, url, fields, url, fields)

    redirects = sum(1 for r in results if r.get("status") == 302)
    assert redirects == 1
    item.refresh_from_db()
    assert item.quantity == Decimal("2")
    assert StockMovement.objects.filter(item=item, kind=StockMovement.Kind.OUT).count() == 1


@pytest.mark.django_db
@requires_postgresql
def test_stock_out_exact_quantity(salon):
    item = InventoryItem.objects.create(
        salon=salon,
        name="exact-qty",
        unit=InventoryItem.Unit.PIECE,
        quantity=Decimal("10"),
        minimum_quantity=Decimal("0"),
    )
    apply_movement(salon=salon, item=item, kind=StockMovement.Kind.OUT, quantity=Decimal("10"))
    item.refresh_from_db()
    assert item.quantity == Decimal("0")
    assert StockMovement.objects.filter(item=item, kind=StockMovement.Kind.OUT).count() == 1


@pytest.mark.django_db
@requires_postgresql
def test_audit_inconsistent_data_read_only_report(salon):
    """Documents drift detection only — does not repair."""
    debt = SalonDebt.objects.create(salon=salon, creditor_name="drift", principal_toman=100, paid_toman=80)
    SalonDebtPayment.objects.create(salon=salon, debt=debt, amount_toman=80)
    SalonDebtPayment.objects.create(salon=salon, debt=debt, amount_toman=80)

    item = InventoryItem.objects.create(
        salon=salon,
        name="neg",
        unit=InventoryItem.Unit.PIECE,
        quantity=Decimal("-6"),
        minimum_quantity=Decimal("0"),
    )
    StockMovement.objects.create(salon=salon, item=item, kind=StockMovement.Kind.OUT, quantity=Decimal("8"))

    debt_issues = audit_debt_payment_consistency(salon=salon)
    inv_issues = audit_inventory_consistency(salon=salon)

    assert len(debt_issues) == 1
    assert debt_issues[0]["paid_toman"] == 80
    assert debt_issues[0]["payments_sum"] == 160

    assert len(inv_issues["negative_stock"]) == 1
    assert inv_issues["negative_stock"][0][2] == Decimal("-6")