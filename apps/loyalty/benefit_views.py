from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.audit.models import AuditLog
from apps.core.fields import TomanAmountField
from apps.core.forms import PersianForm
from apps.customers.models import Customer
from apps.loyalty.benefits import register_referral
from apps.loyalty.models import Referral, LoyaltyVoucher
from apps.salons.decorators import salon_required
from apps.salons.permissions_policy import P_LOYALTY_MANAGE, require_permission


class BenefitForm(PersianForm):
    def __init__(self,*args,salon,**kwargs):
        super().__init__(*args,**kwargs)
        customers=Customer.scoped(salon).filter(is_deleted=False).order_by("full_name","pk")
        for field in self.fields.values():
            if isinstance(field,forms.ModelChoiceField):field.queryset=customers
            field.widget.attrs["class"]="input-field"


class ReferralForm(BenefitForm):
    referrer=forms.ModelChoiceField(queryset=Customer.objects.none(),label="معرف")
    referred=forms.ModelChoiceField(queryset=Customer.objects.none(),label="مشتری جدید")


class VoucherForm(BenefitForm):
    customer=forms.ModelChoiceField(queryset=Customer.objects.none(),label="مشتری")
    title=forms.CharField(max_length=100,label="عنوان تخفیف")
    amount_toman=TomanAmountField(min_value=1,max_value=10**12,label="اعتبار تخفیف (تومان)")
    expires_on=forms.DateField(label="مهلت مصرف",initial=timezone.localdate)

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields["expires_on"].widget.attrs["portal_target"]="#club-voucher"


@salon_required
@require_permission(P_LOYALTY_MANAGE)
@require_http_methods(["GET","POST"])
def referrals(request):
    form=ReferralForm(request.POST if request.method=="POST" else None,salon=request.salon)
    if request.method=="POST" and form.is_valid():
        d=form.cleaned_data
        try:register_referral(salon=request.salon,referrer_id=d["referrer"].pk,referred_id=d["referred"].pk,actor=request.user)
        except ValidationError as exc:form.add_error(None,exc)
        else:return redirect("loyalty:referrals")
    return render(request,"loyalty/referrals.html",{"form":form,"rows":Referral.scoped(request.salon).select_related("referrer","referred").order_by("-pk")[:100]})


@salon_required
@require_permission(P_LOYALTY_MANAGE)
@require_http_methods(["GET","POST"])
def vouchers(request):
    action=request.POST.get("action")
    form=VoucherForm(request.POST if action=="create" else None,salon=request.salon)
    if request.method=="POST" and action=="create" and form.is_valid():
        d=form.cleaned_data
        if d["expires_on"]<timezone.localdate():
            form.add_error("expires_on","مهلت مصرف نباید در گذشته باشد.")
        else:
            with transaction.atomic():
                row=LoyaltyVoucher.objects.create(salon=request.salon,**d)
                AuditLog.objects.create(salon=request.salon,actor=request.user,action=AuditLog.Action.CREATE,entity_type="loyalty_voucher",entity_id=str(row.pk),message="اعتبار اختصاصی مشتری",metadata={"amount_toman":row.amount_toman})
            return redirect("loyalty:vouchers")
    if request.method=="POST" and action=="pause":
        try:
            pk=int(request.POST.get("pk",""))
            if not 0<pk<=2**63-1:raise ValueError
            with transaction.atomic():
                row=LoyaltyVoucher.scoped(request.salon).select_for_update().filter(pk=pk,invoice__isnull=True).first()
                if row and row.is_active:
                    row.is_active=False
                    row.save(update_fields=["is_active","updated_at"])
                    AuditLog.objects.create(salon=request.salon,actor=request.user,action=AuditLog.Action.UPDATE,entity_type="loyalty_voucher",entity_id=str(row.pk),message="غیرفعال کردن اعتبار")
        except (ValueError,TypeError): messages.error(request,"اعتبار معتبر نیست.")
        return redirect("loyalty:vouchers")
    return render(request,"loyalty/vouchers.html",{"form":form,"rows":LoyaltyVoucher.scoped(request.salon).select_related("customer","invoice").order_by("-pk")[:100],"today":timezone.localdate()})
