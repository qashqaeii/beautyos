from datetime import date
from urllib.parse import urlencode

from django import forms
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.audit.models import AuditLog
from apps.core.utils.dates import to_jalali
from apps.dashboard.role_services import day_bounds
from apps.finance.checkout import MAX_MONEY
from apps.finance.models import CashClose, Payment
from apps.salons.decorators import salon_required
from apps.salons.permissions_policy import P_PAYMENT_CREATE, P_PAYMENT_VIEW, has_permission


def cash_totals(salon, day):
    start, end = day_bounds(day)
    rows = Payment.scoped(salon).filter(created_at__gte=start, created_at__lt=end,
        paid_amount_toman__gt=0).exclude(status=Payment.Status.REFUNDED).order_by().values("method").annotate(total=Sum("paid_amount_toman"))
    totals = {row["method"]: int(row["total"]) for row in rows}
    return {method: totals.get(method, 0) for method in Payment.Method.values}


@transaction.atomic
def close_cash_day(*, salon, day, opening, other_in, cash_out, counted, note, actor):
    values = (opening, other_in, cash_out, counted)
    if not isinstance(day, date) or not date(1900, 1, 1) <= day <= timezone.localdate():
        raise ValidationError("روز انتخاب‌شده معتبر نیست.")
    if any(not isinstance(v, int) or not 0 <= v <= MAX_MONEY for v in values):
        raise ValidationError("مبالغ صندوق معتبر نیستند.")
    note = (note or "").strip()
    if len(note) > 500:
        raise ValidationError("توضیحات بیش از حد طولانی است.")
    recorded = {"opening_toman": opening, "other_in_toman": other_in, "cash_out_toman": cash_out,
                "counted_toman": counted, "note": note}
    def check(existing):
        if any(getattr(existing, field) != value for field, value in recorded.items()):
            raise ValidationError("صندوق این روز قبلاً بسته شده است؛ ثبت دوباره مجاز نیست.")
        return existing
    previous = CashClose.scoped(salon).filter(day=day).first()
    if previous:
        return check(previous)
    totals = cash_totals(salon, day)
    expected = opening + totals["cash"] + other_in - cash_out
    difference = counted - expected
    if any(abs(value) > MAX_MONEY for value in (*totals.values(), expected, difference)):
        raise ValidationError("مبالغ خارج از محدوده قابل ثبت هستند.")
    if difference and not note:
        raise ValidationError("علت مغایرت صندوق را توضیح دهید.")
    close, created = CashClose.objects.get_or_create(salon=salon, day=day, defaults={
        **recorded, "cash_received_toman": totals["cash"], "card_received_toman": totals["card"],
        "transfer_received_toman": totals["transfer"], "expected_toman": expected,
        "difference_toman": difference, "closed_by": actor,
    })
    if not created:
        return check(close)
    AuditLog.objects.create(salon=salon, actor=actor, action=AuditLog.Action.CREATE,
        entity_type="cash_close",entity_id=str(close.pk),message="بستن صندوق روزانه",
        metadata={"day":day.isoformat(),"expected":expected,"counted":counted,"difference":difference})
    return close


class CashCloseForm(forms.Form):
    opening = forms.IntegerField(min_value=0, max_value=MAX_MONEY,label="موجودی نقدی ابتدای روز")
    other_in = forms.IntegerField(min_value=0,max_value=MAX_MONEY,required=False,label="سایر ورود وجه نقد")
    cash_out = forms.IntegerField(min_value=0,max_value=MAX_MONEY,required=False,label="خروج وجه نقد")
    counted = forms.IntegerField(min_value=0,max_value=MAX_MONEY,label="وجه نقد شمارش‌شده")
    note = forms.CharField(required=False,max_length=500,label="توضیح مغایرت یا گردش نقدی",widget=forms.Textarea(attrs={"rows":2}))
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"]="input-field"


@salon_required
@require_http_methods(["GET","POST"])
def cash_close_view(request):
    membership = getattr(request,"membership",None)
    if not (has_permission(membership,P_PAYMENT_CREATE) and has_permission(membership,P_PAYMENT_VIEW)):
        raise PermissionDenied
    today=timezone.localdate()
    raw=request.POST.get("day") if request.method=="POST" else request.GET.get("day")
    try:
        day=date.fromisoformat(raw) if raw else today
        if not date(1900,1,1)<=day<=today:
            raise ValueError
    except (ValueError,TypeError):
        if request.method=="POST":
            return render(request,"finance/cash_close.html",{
                "day":today,"day_jalali":to_jalali(today),"totals":cash_totals(request.salon,today),
                "close":CashClose.scoped(request.salon).filter(day=today).first(),
                "form":CashCloseForm(),"invalid_day":True},status=400)
        day=today
    form=CashCloseForm(request.POST if request.method=="POST" else None,initial={"opening":0,"other_in":0,"cash_out":0})
    if request.method=="POST" and form.is_valid():
        data=form.cleaned_data
        try:
            close_cash_day(salon=request.salon,day=day,opening=data["opening"],other_in=data["other_in"] or 0,
                cash_out=data["cash_out"] or 0,counted=data["counted"],note=data["note"],actor=request.user)
        except ValidationError as exc:
            form.add_error(None,exc)
        else:
            return redirect(reverse("finance:cash_close")+"?"+urlencode({"day":day.isoformat()}))
    totals=cash_totals(request.salon,day)
    close=CashClose.scoped(request.salon).filter(day=day).first()
    return render(request,"finance/cash_close.html",{
        "day":day,"day_jalali":to_jalali(day),"form":form,"totals":totals,"close":close,
        "late_cash_delta":totals["cash"]-close.cash_received_toman if close else 0,
        "late_card_delta":totals["card"]-close.card_received_toman if close else 0,
        "late_transfer_delta":totals["transfer"]-close.transfer_received_toman if close else 0,
        "history":CashClose.scoped(request.salon).order_by("-day")[:10],
    })
