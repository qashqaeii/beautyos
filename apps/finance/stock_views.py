from uuid import uuid4

from django import forms
from apps.core.fields import TomanAmountField
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.appointments.models import Appointment
from apps.customers.models import Customer
from apps.finance.ledger import MAX_MONEY
from apps.finance.ledger_views import StyledForm, RefundForm
from apps.finance.models import MaterialCost, Payment, ProductSale
from apps.finance.stock_finance import consume_material, return_product, sell_product, set_unit_cost
from apps.inventory.models import InventoryItem
from apps.salons.decorators import salon_required
from apps.salons.permissions_policy import P_PAYMENT_CREATE, P_FINANCE_REPORTS, P_INVENTORY_MANAGE, has_permission, require_permission


class ItemForm(StyledForm):
    item=forms.ModelChoiceField(queryset=InventoryItem.objects.none(),label="کالا")
    def __init__(self,*args,salon,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields["item"].queryset=InventoryItem.scoped(salon).order_by("name","pk")
        self.fields["item"].label_from_instance=lambda item:f"{item.name} · {item.unit} · موجودی {item.quantity}"

class CostForm(ItemForm):
    unit_cost=TomanAmountField(min_value=1,max_value=MAX_MONEY,label="بهای خرید هر واحد (تومان)")

class SaleForm(ItemForm):
    customer=forms.ModelChoiceField(queryset=Customer.objects.none(),label="مشتری")
    quantity=forms.DecimalField(min_value=0.01,max_digits=12,decimal_places=2,label="تعداد / مقدار")
    unit_price=TomanAmountField(min_value=1,max_value=MAX_MONEY,label="قیمت فروش هر واحد (تومان)")
    method=forms.ChoiceField(choices=Payment.Method.choices,label="روش دریافت")
    request_key=forms.UUIDField(widget=forms.HiddenInput)
    def __init__(self,*args,salon,**kwargs):
        super().__init__(*args,salon=salon,**kwargs)
        self.fields["customer"].queryset=Customer.scoped(salon).filter(is_deleted=False).order_by("full_name","pk")
        self.fields["customer"].label_from_instance=lambda row:f"{row.full_name} · {row.phone}"

class ConsumeForm(ItemForm):
    appointment=forms.ModelChoiceField(queryset=Appointment.objects.none(),label="نوبت")
    quantity=forms.DecimalField(min_value=0.01,max_digits=12,decimal_places=2,label="مقدار مصرف")
    request_key=forms.UUIDField(widget=forms.HiddenInput)
    def __init__(self,*args,salon,**kwargs):
        super().__init__(*args,salon=salon,**kwargs)
        self.fields["appointment"].queryset=Appointment.scoped(salon).filter(status__in=(Appointment.Status.CHECKED_IN,Appointment.Status.COMPLETED)).select_related("customer","service").order_by("-start_at","-pk")
        self.fields["appointment"].label_from_instance=lambda row:f"{row.customer.full_name} · {row.service.name}"


@salon_required
@require_permission(P_PAYMENT_CREATE)
@require_http_methods(["GET","POST"])
def product_sales(request):
    form=SaleForm(request.POST if request.method=="POST" else None,salon=request.salon,initial={"request_key":uuid4()})
    can_report=has_permission(request.membership,P_FINANCE_REPORTS)
    if request.method=="POST" and form.is_valid():
        d=form.cleaned_data
        try:
            sale=sell_product(salon=request.salon,customer_id=d["customer"].pk,item_id=d["item"].pk,quantity=d["quantity"],
                unit_price=d["unit_price"],method=d["method"],request_key=d["request_key"],actor=request.user)
        except ValidationError as exc:form.add_error(None,exc)
        else:return redirect("finance:receipt",payment_id=sale.payment_id)
    return render(request,"finance/product_sales.html",{"form":form,"can_report":can_report,
        "sales":ProductSale.scoped(request.salon).select_related("payment__customer","return_record").order_by("-pk")[:40] if can_report else []})


@salon_required
@require_permission(P_FINANCE_REPORTS)
@require_http_methods(["GET","POST"])
def product_return(request,sale_id):
    sale=get_object_or_404(ProductSale.scoped(request.salon).select_related("payment","item"),pk=sale_id)
    class ReturnForm(StyledForm):
        request_key=forms.UUIDField(widget=forms.HiddenInput)
        reason=forms.CharField(max_length=255,label="علت برگشت کالا")
    form=ReturnForm(request.POST if request.method=="POST" else None,initial={"request_key":uuid4()})
    if request.method=="POST" and form.is_valid():
        try:return_product(salon=request.salon,sale_id=sale.pk,reason=form.cleaned_data["reason"],request_key=form.cleaned_data["request_key"],actor=request.user)
        except ValidationError as exc:form.add_error(None,exc)
        else:return redirect("finance:receipt",payment_id=sale.payment_id)
    return render(request,"finance/product_return.html",{"sale":sale,"form":form})


@salon_required
@require_permission(P_INVENTORY_MANAGE)
@require_http_methods(["GET","POST"])
def materials(request):
    salon=request.salon
    action=request.POST.get("action")
    cost=CostForm(request.POST if action=="cost" else None,salon=salon,auto_id="cost_%s")
    consume=ConsumeForm(request.POST if action=="consume" else None,salon=salon,
        initial={"request_key":uuid4()},auto_id="consume_%s")
    if request.method=="POST":
        form={"cost":cost,"consume":consume}.get(action)
        if form and form.is_valid():
            d=form.cleaned_data
            try:
                if action=="cost":set_unit_cost(salon=salon,item_id=d["item"].pk,unit_cost=d["unit_cost"],actor=request.user)
                else:consume_material(salon=salon,appointment_id=d["appointment"].pk,item_id=d["item"].pk,quantity=d["quantity"],request_key=d["request_key"],actor=request.user)
            except ValidationError as exc:form.add_error(None,exc)
            else:return redirect("finance:materials")
    return render(request,"finance/materials.html",{"cost_form":cost,"consume_form":consume,
        "items":InventoryItem.scoped(salon).order_by("name")[:50],
        "costs":MaterialCost.scoped(salon).select_related("appointment__service","movement").order_by("-pk")[:40]})
