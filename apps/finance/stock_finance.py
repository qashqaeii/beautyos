from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.appointments.models import Appointment
from apps.customers.models import Customer
from apps.customers.services import refresh_customer_stats
from apps.finance.ledger import MAX_MONEY, _audit, _key, _positive
from apps.finance.models import MaterialCost, Payment, ProductReturn, ProductSale, Refund
from apps.inventory.models import InventoryItem, StockMovement
from apps.inventory.services import apply_movement


def quantity_value(value):
    try:
        qty=Decimal(str(value))
        if not qty.is_finite() or not Decimal("0.01")<=qty<=Decimal("9999999999.99") or qty!=qty.quantize(Decimal("0.01")):
            raise ValueError
    except (ValueError,InvalidOperation,TypeError):
        raise ValidationError("مقدار کالا معتبر نیست.") from None
    return qty


def money(quantity, unit):
    value=int((quantity*Decimal(unit)).quantize(Decimal("1"),rounding=ROUND_HALF_UP))
    if not 0<=value<=MAX_MONEY: raise ValidationError("مبلغ خارج از محدوده است.")
    return value


@transaction.atomic
def set_unit_cost(*,salon,item_id,unit_cost,actor):
    _positive(unit_cost)
    item=InventoryItem.scoped(salon).select_for_update().filter(pk=item_id).first()
    if not item: raise ValidationError("کالا یافت نشد.")
    if item.purchase_price_toman!=unit_cost:
        item.purchase_price_toman=unit_cost
        item.save(update_fields=["purchase_price_toman","updated_at"])
        _audit(salon,actor,item,"inventory_item","تعیین بهای واحد",{"unit_cost":unit_cost})
    return item


@transaction.atomic
def sell_product(*,salon,customer_id,item_id,quantity,unit_price,method,request_key,actor):
    qty=quantity_value(quantity)
    _positive(unit_price)
    key=_key(request_key)
    if method not in Payment.Method.values: raise ValidationError("روش پرداخت معتبر نیست.")
    customer=Customer.scoped(salon).filter(pk=customer_id,is_deleted=False).first()
    item=InventoryItem.scoped(salon).select_for_update().filter(pk=item_id).first()
    if not item or not customer: raise ValidationError("کالا یا مشتری معتبر نیست.")
    previous=ProductSale.scoped(salon).filter(request_key=key).select_related("payment").first()
    if previous:
        if (previous.payment.customer_id,previous.item_id,previous.quantity,previous.unit_price_toman,previous.payment.method)!=(customer_id,item_id,qty,unit_price,method):
            raise ValidationError("درخواست قبلاً با اطلاعات متفاوت ثبت شده است.")
        return previous
    if item.purchase_price_toman<=0: raise ValidationError("ابتدا بهای خرید هر واحد کالا را تنظیم کنید.")
    revenue=money(qty,unit_price)
    _positive(revenue)
    cost=money(qty,item.purchase_price_toman)
    movement=apply_movement(salon=salon,item=item,kind=StockMovement.Kind.OUT,quantity=qty,note="فروش صندوق")
    payment=Payment.objects.create(salon=salon,customer=customer,total_amount_toman=revenue,paid_amount_toman=revenue,
        method=method,status=Payment.Status.PAID,notes="فروش محصول")
    # Same transaction: a racing request key rolls back stock and payment as well.
    try:
        sale=ProductSale.objects.create(salon=salon,item=item,payment=payment,movement=movement,item_name=item.name,
            quantity=qty,unit_price_toman=unit_price,unit_cost_toman=item.purchase_price_toman,
            revenue_toman=revenue,cost_toman=cost,request_key=key)
    except IntegrityError as exc:
        raise ValidationError("درخواست تکراری است.") from exc
    from apps.loyalty.automation import award_payment
    award_payment(payment)
    refresh_customer_stats(customer)
    _audit(salon,actor,sale,"product_sale","فروش محصول",{"revenue":revenue,"cost":cost,"payment_id":payment.pk})
    return sale


@transaction.atomic
def return_product(*,salon,sale_id,reason,request_key,actor):
    key=_key(request_key)
    reason=(reason or "").strip()
    if not reason or len(reason)>255: raise ValidationError("علت برگشت را وارد کنید.")
    sale=ProductSale.scoped(salon).select_for_update(of=("self",)).select_related("payment","item").filter(pk=sale_id).first()
    if not sale: raise ValidationError("فروش یافت نشد.")
    previous=ProductReturn.scoped(salon).filter(sale=sale).select_related("refund").first()
    if previous:
        if previous.refund.request_key==key and previous.refund.reason==reason:return previous
        raise ValidationError("این فروش قبلاً برگشت خورده است.")
    payment=Payment.scoped(salon).select_for_update().get(pk=sale.payment_id)
    if payment.status==Payment.Status.REFUNDED or payment.refunds.exists():
        raise ValidationError("سوابق استرداد نیازمند بررسی هستند.")
    if Refund.scoped(salon).filter(request_key=key).exists(): raise ValidationError("شناسه درخواست تکراری است.")
    movement=apply_movement(salon=salon,item=sale.item,kind=StockMovement.Kind.IN,quantity=sale.quantity,note="برگشت محصول")
    try:
        refund=Refund.objects.create(salon=salon,payment=payment,request_key=key,amount_toman=sale.revenue_toman,reason=reason)
    except IntegrityError as exc:
        raise ValidationError("شناسه درخواست تکراری است.") from exc
    row=ProductReturn.objects.create(salon=salon,sale=sale,refund=refund,movement=movement)
    from apps.loyalty.automation import reconcile_refund
    reconcile_refund(payment)
    refresh_customer_stats(payment.customer)
    _audit(salon,actor,row,"product_return","برگشت محصول و وجه",{"sale_id":sale.pk,"refund_id":refund.pk})
    return row


@transaction.atomic
def consume_material(*,salon,appointment_id,item_id,quantity,request_key,actor):
    qty=quantity_value(quantity)
    key=_key(request_key)
    appointment=Appointment.scoped(salon).select_for_update().filter(pk=appointment_id).first()
    item=InventoryItem.scoped(salon).select_for_update().filter(pk=item_id).first()
    if not appointment or not item or appointment.status not in (Appointment.Status.CHECKED_IN,Appointment.Status.COMPLETED):
        raise ValidationError("نوبت پذیرش‌شده یا انجام‌شده و کالا را انتخاب کنید.")
    previous=MaterialCost.scoped(salon).filter(request_key=key).select_related("movement").first()
    if previous:
        if (previous.appointment_id,previous.movement.item_id,previous.movement.quantity)!=(appointment_id,item_id,qty):
            raise ValidationError("درخواست قبلاً با اطلاعات متفاوت ثبت شده است.")
        return previous
    if item.purchase_price_toman<=0: raise ValidationError("ابتدا بهای خرید هر واحد را وارد کنید.")
    cost=money(qty,item.purchase_price_toman)
    movement=apply_movement(salon=salon,item=item,kind=StockMovement.Kind.OUT,quantity=qty,
        note="مصرف مواد در خدمت",appointment=appointment)
    try:
        row=MaterialCost.objects.create(salon=salon,appointment=appointment,movement=movement,
            item_name=item.name,unit_cost_toman=item.purchase_price_toman,cost_toman=cost,request_key=key)
    except IntegrityError as exc:
        raise ValidationError("درخواست تکراری است.") from exc
    _audit(salon,actor,row,"material_cost","مصرف مواد خدمت",{"appointment_id":appointment.pk,"cost":cost})
    return row
