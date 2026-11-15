"""جست‌وجوی سبک مشتری برای انتخابگر نوبت."""

from __future__ import annotations

from apps.core.utils.phone import display_iran_mobile
from apps.customers.models import Customer
from apps.customers.queries import filter_customers


def search_customers_for_picker(salon, query: str, *, limit: int = 10):
    q = (query or "").strip()
    if len(q) < 1:
        return []
    qs = filter_customers(salon, q=q, ordering="name")[:limit]
    return [
        {
            "id": c.pk,
            "full_name": c.full_name,
            "phone_display": display_iran_mobile(c.phone),
        }
        for c in qs
    ]


def find_customer_by_phone(salon, phone_e164: str) -> Customer | None:
    return Customer.scoped(salon).filter(phone=phone_e164, is_deleted=False).first()
