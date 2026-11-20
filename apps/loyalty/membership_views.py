from datetime import timedelta
from uuid import uuid4

from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.customers.models import Customer
from apps.loyalty.insights import loyalty_insights
from apps.loyalty.memberships import buy_membership
from apps.loyalty.models import MembershipCycle
from apps.packages.models import ServicePackage
from apps.salons.decorators import salon_required
from apps.salons.permissions_policy import P_LOYALTY_MANAGE, require_permission


class MembershipForm(forms.Form):
    customer=forms.ModelChoiceField(queryset=Customer.objects.none(),label="مشتری")
    package=forms.ModelChoiceField(queryset=ServicePackage.objects.none(),label="پکیج عضویت")
    request_key=forms.UUIDField(widget=forms.HiddenInput)
    def __init__(self,*args,salon,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields["customer"].queryset=Customer.scoped(salon).filter(is_deleted=False).order_by("full_name","pk")
        self.fields["package"].queryset=ServicePackage.scoped(salon).filter(is_active=True).order_by("name","pk")
        self.fields["package"].label_from_instance=lambda p:f"{p.name} · {p.price_toman:,} تومان · {p.validity_days} روز"
        for field in self.visible_fields():field.field.widget.attrs["class"]="input-field"


@salon_required
@require_permission(P_LOYALTY_MANAGE)
@require_http_methods(["GET","POST"])
def memberships(request):
    salon=request.salon
    action=request.POST.get("action")
    form=MembershipForm(request.POST if action=="buy" else None,salon=salon,initial={"request_key":uuid4()})
    if request.method=="POST":
        if action=="buy" and form.is_valid():
            d=form.cleaned_data
            try:buy_membership(salon=salon,customer_id=d["customer"].pk,package_id=d["package"].pk,request_key=d["request_key"],actor=request.user)
            except ValidationError as exc:form.add_error(None,exc)
            else:return redirect("loyalty:memberships")
        if action=="renew":
            try:
                pk=int(request.POST.get("cycle",""))
                if not 0<pk<=2**63-1:raise ValueError
                row=MembershipCycle.scoped(salon).select_related("purchase").filter(pk=pk).first()
                if not row:raise ValidationError("عضویت یافت نشد.")
                buy_membership(salon=salon,customer_id=row.purchase.customer_id,package_id=row.purchase.package_id,
                    renewed_from_id=row.pk,request_key=request.POST.get("request_key"),actor=request.user)
            except (ValueError,TypeError,ValidationError) as exc:messages.error(request,str(exc) or "درخواست معتبر نیست.")
            else:messages.success(request,"تمدید ثبت شد.")
            return redirect("loyalty:memberships")
    qs=MembershipCycle.scoped(salon).select_related("purchase__customer","purchase__package","renewal")
    rows=[]
    now=timezone.now()
    for row in qs.order_by("-pk")[:100]:
        active=row.purchase.is_valid()
        can_renew=not active and not hasattr(row,"renewal") and row.purchase.package.is_active and not row.purchase.customer.is_deleted
        rows.append({"cycle":row,"active":active,"expiring":active and row.purchase.expires_at<=now+timedelta(days=7),
            "can_renew":can_renew,"request_key":uuid4()})
    return render(request,"loyalty/memberships.html",{"form":form,"rows":rows})


@salon_required
@require_permission(P_LOYALTY_MANAGE)
@require_http_methods(["GET"])
def insights(request):
    return render(request,"loyalty/insights.html",{"data":loyalty_insights(request.salon)})
