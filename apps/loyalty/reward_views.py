from uuid import uuid4

from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.audit.models import AuditLog
from apps.customers.models import Customer
from apps.loyalty.models import LoyaltyAccount, LoyaltyAward, LoyaltyReward, RewardRedemption
from apps.loyalty.automation import active_policy
from apps.loyalty.rewards import birthday_month, birthday_source_key, claim_birthday, change_redemption, redeem_reward
from apps.salons.decorators import salon_required
from apps.salons.permissions_policy import P_LOYALTY_MANAGE, require_permission


class RewardForm(forms.Form):
    title=forms.CharField(max_length=100,label="نام پاداش")
    description=forms.CharField(max_length=255,required=False,label="شرایط دریافت")
    points_cost=forms.IntegerField(min_value=1,max_value=1000000,label="امتیاز لازم")
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"]="input-field"


class RedeemForm(forms.Form):
    account=forms.ModelChoiceField(queryset=LoyaltyAccount.objects.none(),label="عضو باشگاه")
    reward=forms.ModelChoiceField(queryset=LoyaltyReward.objects.none(),label="پاداش")
    request_key=forms.UUIDField(widget=forms.HiddenInput)

    def __init__(self,*args,salon,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields["account"].queryset=LoyaltyAccount.scoped(salon).filter(customer__salon=salon,customer__is_deleted=False).select_related("customer").order_by("customer__full_name")
        self.fields["account"].label_from_instance=lambda row:f"{row.customer.full_name} · {row.points_balance:,} امتیاز"
        self.fields["reward"].queryset=LoyaltyReward.scoped(salon).order_by("title")
        self.fields["reward"].label_from_instance=lambda row:f"{row.title} · {row.points_cost:,} امتیاز" + ("" if row.is_active else " · غیرفعال")
        for field in self.visible_fields():
            field.field.widget.attrs["class"]="input-field"


def _pk(raw):
    value=int(raw)
    if not 0<value<=2**63-1:
        raise ValueError
    return value


@salon_required
@require_permission(P_LOYALTY_MANAGE)
@require_http_methods(["GET","POST"])
def rewards(request):
    salon=request.salon
    action=request.POST.get("action")
    create=RewardForm(request.POST if action=="create" else None,auto_id="reward_%s")
    redeem=RedeemForm(request.POST if action=="redeem" else None,salon=salon,initial={"request_key":uuid4()},auto_id="redeem_%s")
    if request.method=="POST":
        if action=="create" and create.is_valid():
            from django.db import transaction
            with transaction.atomic():
                obj=LoyaltyReward.objects.create(salon=salon,**create.cleaned_data)
                AuditLog.objects.create(salon=salon,actor=request.user,action=AuditLog.Action.CREATE,entity_type="loyalty_reward",entity_id=str(obj.pk),message="تعریف پاداش باشگاه")
            return redirect("loyalty:rewards")
        elif action=="redeem" and redeem.is_valid():
            fields=redeem.cleaned_data
            try:
                redeem_reward(salon=salon,account_id=fields["account"].pk,reward_id=fields["reward"].pk,
                    request_key=fields["request_key"],actor=request.user)
            except ValidationError as exc:
                redeem.add_error(None,exc)
            else:
                return redirect("loyalty:rewards")
        elif action in ("fulfilled","cancelled","activate","pause"):
            try:
                pk=_pk(request.POST.get("pk",""))
                if action in ("fulfilled","cancelled"):
                    change_redemption(salon=salon,redemption_id=pk,status=action,actor=request.user)
                else:
                    from django.db import transaction
                    with transaction.atomic():
                        reward=LoyaltyReward.scoped(salon).select_for_update().filter(pk=pk).first()
                        if not reward:
                            raise ValidationError("پاداش یافت نشد.")
                        reward.is_active=action=="activate"
                        reward.save(update_fields=["is_active","updated_at"])
                        AuditLog.objects.create(salon=salon,actor=request.user,action=AuditLog.Action.UPDATE,
                            entity_type="loyalty_reward",entity_id=str(reward.pk),message="تغییر دسترسی پاداش")
            except (ValueError,TypeError,ValidationError) as exc:
                messages.error(request,str(exc) or "درخواست معتبر نیست.")
            return redirect("loyalty:rewards")
    return render(request,"loyalty/rewards.html",{"create_form":create,"redeem_form":redeem,
        "rewards":LoyaltyReward.scoped(salon).order_by("-is_active","title"),
        "redemptions":RewardRedemption.scoped(salon).select_related("account__customer").order_by("-pk")[:60]})


@salon_required
@require_permission(P_LOYALTY_MANAGE)
@require_http_methods(["GET","POST"])
def birthdays(request):
    salon=request.salon
    if request.method=="POST":
        try:
            pk=_pk(request.POST.get("customer",""))
            customer=Customer.scoped(salon).filter(pk=pk,is_deleted=False).first()
            if customer is None: raise ValidationError("مشتری یافت نشد.")
            claim_birthday(salon=salon,customer=customer,actor=request.user)
            messages.success(request,"هدیه تولد این سال ثبت شده است.")
        except (ValueError,TypeError,ValidationError) as exc:
            messages.error(request,str(exc) or "درخواست معتبر نیست.")
        return redirect("loyalty:birthdays")
    customers=[c for c in Customer.scoped(salon).filter(is_deleted=False,birth_date__isnull=False).order_by("full_name") if birthday_month(c)]
    keys={birthday_source_key(c) for c in customers}
    claimed=set(LoyaltyAward.scoped(salon).filter(source_kind="birthday",source_key__in=keys).values_list("source_key",flat=True))
    rows=[{"customer":c,"claimed":birthday_source_key(c) in claimed} for c in customers]
    return render(request,"loyalty/birthdays.html",{"rows":rows,"policy":active_policy(salon)})
