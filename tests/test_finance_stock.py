from uuid import uuid4
from decimal import Decimal
from datetime import timedelta
import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from apps.appointments.models import Appointment
from apps.customers.models import Customer
from apps.finance.models import ProductSale, Refund
from apps.finance.stock_finance import set_unit_cost, sell_product, return_product, consume_material
from apps.inventory.models import InventoryItem
from apps.services.models import Service
from apps.staff.models import StaffProfile

@pytest.mark.django_db
def test_sale_return_and_cost_snapshot(client,salon,owner_membership):
    actor=owner_membership.user
    customer=Customer.objects.create(salon=salon,full_name="مشتری",phone="+989121231199")
    item=InventoryItem.objects.create(salon=salon,name="کالا",quantity=10)
    set_unit_cost(salon=salon,item_id=item.pk,unit_cost=50000,actor=actor)
    args=dict(salon=salon,customer_id=customer.pk,item_id=item.pk,quantity=Decimal("2"),unit_price=80000,method="card",request_key=uuid4(),actor=actor)
    sale=sell_product(**args)
    assert sale.cost_toman==100000 and sale.revenue_toman==160000
    assert sell_product(**args).pk==sale.pk
    item.refresh_from_db()
    assert item.quantity==8
    client.force_login(actor)
    assert client.get(reverse("finance:product_sales")).status_code==200
    assert client.get(reverse("finance:materials")).status_code==200
    assert client.get(reverse("finance:receipt",args=[sale.payment_id])).status_code==200
    returned=return_product(salon=salon,sale_id=sale.pk,reason="برگشت",request_key=uuid4(),actor=actor)
    assert returned.refund.amount_toman==160000
    item.refresh_from_db()
    assert item.quantity==10
    staff,_=StaffProfile.objects.get_or_create(salon=salon,membership=owner_membership)
    service=Service.objects.create(salon=salon,name="خدمت",price_toman=300000)
    now=timezone.now()
    appointment=Appointment.objects.create(salon=salon,customer=customer,staff=staff,service=service,start_at=now,
        end_at=now+timedelta(minutes=30),status=Appointment.Status.CHECKED_IN,price_toman=300000)
    row=consume_material(salon=salon,appointment_id=appointment.pk,item_id=item.pk,quantity=Decimal("0.5"),request_key=uuid4(),actor=actor)
    assert row.cost_toman==25000
    set_unit_cost(salon=salon,item_id=item.pk,unit_cost=80000,actor=actor)
    row.refresh_from_db()
    assert row.cost_toman==25000
    assert ProductSale.scoped(salon).count()==1 and Refund.scoped(salon).count()==1
