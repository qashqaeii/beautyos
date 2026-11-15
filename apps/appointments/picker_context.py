from __future__ import annotations

from apps.core.utils.phone import display_iran_mobile
from apps.customers.models import Customer
from apps.salons.permissions_policy import P_CUSTOMER_CREATE, P_CUSTOMER_VIEW, has_permission


def resolve_customer_picker_context(*, form, membership, salon) -> dict:
    can_create = has_permission(membership, P_CUSTOMER_CREATE)
    can_search = has_permission(membership, P_CUSTOMER_VIEW)

    customer_pk = None
    if form.is_bound:
        raw_id = (form.data.get("customer") or "").strip()
        if raw_id:
            customer_pk = raw_id
    else:
        cust = form.initial.get("customer")
        if cust:
            customer_pk = str(cust.pk if isinstance(cust, Customer) else cust)

    selected_display = None
    if customer_pk:
        inst = Customer.scoped(salon).filter(pk=customer_pk, is_deleted=False).first()
        if inst:
            selected_display = {
                "full_name": inst.full_name,
                "phone_display": display_iran_mobile(inst.phone),
            }
        else:
            customer_pk = None

    if not can_create and not can_search:
        mode = "none"
    elif not can_create:
        mode = "search"
    elif customer_pk and selected_display:
        mode = "selected"
    elif form.is_bound:
        if form.data.get("customer") and selected_display:
            mode = "selected"
        elif form.data.get("new_customer_mode"):
            mode = "new"
        elif any(
            (
                (form.data.get("new_customer_first_name") or "").strip(),
                (form.data.get("new_customer_last_name") or "").strip(),
                (form.data.get("new_customer_phone") or "").strip(),
            )
        ):
            mode = "new"
        elif (form.data.get("customer_search") or "").strip() and not form.data.get("customer"):
            mode = "search"
        else:
            mode = "new"
    else:
        mode = "new"

    return {
        "picker_initial_mode": mode,
        "selected_customer_display": selected_display,
        "perms_customer_create": can_create,
        "perms_customer_search": can_search,
        "customer_picker_config": {
            "searchUrl": "",
            "customerId": customer_pk or "",
            "initialQuery": (
                (form.data.get("customer_search") if form.is_bound else form.initial.get("customer_search", "")) or ""
            ),
            "initialMode": mode,
            "selectedName": (selected_display or {}).get("full_name", ""),
            "selectedPhone": (selected_display or {}).get("phone_display", ""),
            "firstName": (form["new_customer_first_name"].value() if "new_customer_first_name" in form.fields else "")
            or "",
            "lastName": (form["new_customer_last_name"].value() if "new_customer_last_name" in form.fields else "")
            or "",
            "newPhone": (form["new_customer_phone"].value() if "new_customer_phone" in form.fields else "") or "",
            "canCreateCustomer": can_create,
            "searchOnly": not can_create and can_search,
        },
    }
