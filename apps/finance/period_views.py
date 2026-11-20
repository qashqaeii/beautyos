from datetime import date
from uuid import uuid4

import jdatetime
from django import forms
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.expenses.models import Expense
from apps.finance.ledger import MAX_MONEY, amount_sum
from apps.finance.ledger_views import StyledForm
from apps.finance.models import StaffAgreement, StaffPeriod, RecurringExpense
from apps.finance.periods import create_agreement, open_staff_period, pay_staff_period, record_recurring_expense
from apps.salons.decorators import salon_required
from apps.salons.permissions_policy import P_COMMISSION_MANAGE, P_EXPENSE_MANAGE, require_permission
from apps.staff.models import StaffProfile


class StaffForm(StyledForm):
    staff=forms.ModelChoiceField(queryset=StaffProfile.objects.none(),label="متخصص")
    month=forms.DateField(label="ماه مورد نظر (یک روز از ماه)",initial=timezone.localdate)
    def __init__(self,*args,salon,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields["staff"].queryset=StaffProfile.scoped(salon).filter(is_deleted=False).order_by("display_name")

class AgreementForm(StaffForm):
    mode=forms.ChoiceField(choices=StaffAgreement._meta.get_field("mode").choices,label="نوع همکاری")
    amount=forms.IntegerField(min_value=0,max_value=MAX_MONEY,label="حقوق یا اجاره ماهانه (تومان)",initial=0)

class PeriodPaymentForm(StyledForm):
    period=forms.ModelChoiceField(queryset=StaffPeriod.objects.none(),label="تعهد ماهانه")
    kind=forms.ChoiceField(choices=[("advance","مساعده حقوق"),("settlement","تسویه حقوق"),("rent","دریافت اجاره")],label="نوع عملیات")
    amount=forms.IntegerField(min_value=1,max_value=MAX_MONEY,label="مبلغ (تومان)")
    note=forms.CharField(max_length=255,required=False,label="توضیح")
    request_key=forms.UUIDField(widget=forms.HiddenInput)
    def __init__(self,*args,salon,**kwargs):
        super().__init__(*args,**kwargs)
        from apps.core.utils.dates import to_jalali
        self.fields["period"].queryset=StaffPeriod.scoped(salon).select_related("staff").order_by("-month","-pk")
        self.fields["period"].label_from_instance=lambda row:f"{row.staff.full_display_name} · {to_jalali(row.month)} · {row.get_kind_display()}"

@salon_required
@require_permission(P_COMMISSION_MANAGE)
@require_http_methods(["GET","POST"])
def staff_finance(request):
    salon=request.salon
    action=request.POST.get("action")
    agreement=AgreementForm(request.POST if action=="agreement" else None,salon=salon,auto_id="agreement_%s")
    period=StaffForm(request.POST if action=="period" else None,salon=salon,auto_id="period_%s")
    payment=PeriodPaymentForm(request.POST if action=="payment" else None,salon=salon,
        initial={"request_key":uuid4()},auto_id="payment_%s")
    if request.method=="POST":
        form={"agreement":agreement,"period":period,"payment":payment}.get(action)
        if form and form.is_valid():
            d=form.cleaned_data
            try:
                if action=="agreement": create_agreement(salon=salon,staff_id=d["staff"].pk,month=d["month"],mode=d["mode"],amount=d["amount"],actor=request.user)
                elif action=="period": open_staff_period(salon=salon,staff_id=d["staff"].pk,month=d["month"],actor=request.user)
                else: pay_staff_period(salon=salon,period_id=d["period"].pk,kind=d["kind"],amount=d["amount"],note=d["note"],request_key=d["request_key"],actor=request.user)
            except ValidationError as exc: form.add_error(None,exc)
            else: return redirect("finance:staff_finance")
    rows=[]
    for row in StaffPeriod.scoped(salon).select_related("staff").order_by("-month","-pk")[:50]:
        paid=amount_sum(row.payments.filter(salon=salon))
        rows.append({"period":row,"paid":paid,"balance":row.amount_toman-paid})
    return render(request,"finance/staff_finance.html",{"agreement_form":agreement,"period_form":period,
        "payment_form":payment,"rows":rows,"agreements":StaffAgreement.scoped(salon).select_related("staff").order_by("-effective_month","-pk")[:30]})


class RecurringForm(StyledForm):
    title=forms.CharField(max_length=120,label="عنوان هزینه")
    category=forms.ChoiceField(choices=Expense.Category.choices,label="دسته‌بندی")
    amount_toman=forms.IntegerField(min_value=1,max_value=MAX_MONEY,label="مبلغ (تومان)")
    next_due=forms.DateField(label="اولین سررسید",initial=timezone.localdate)

@salon_required
@require_permission(P_EXPENSE_MANAGE)
@require_http_methods(["GET","POST"])
def recurring_expenses(request):
    salon=request.salon
    action=request.POST.get("action")
    form=RecurringForm(request.POST if action=="create" else None)
    error=""
    if request.method=="POST":
        if action=="create" and form.is_valid():
            d=form.cleaned_data
            if d["next_due"]<timezone.localdate():
                form.add_error("next_due","اولین سررسید نباید در گذشته باشد.")
            else:
                RecurringExpense.objects.create(salon=salon,day_of_month=jdatetime.date.fromgregorian(date=d["next_due"]).day,**d)
                return redirect("finance:recurring")
        elif action in ("record","pause"):
            try:
                pk=int(request.POST.get("schedule",""))
                if not 0<pk<=MAX_MONEY: raise ValueError
                if action=="record":
                    record_recurring_expense(salon=salon,schedule_id=pk,expected_due=date.fromisoformat(request.POST.get("due","")),actor=request.user)
                else:
                    RecurringExpense.scoped(salon).filter(pk=pk).update(is_active=False)
            except (ValueError,ValidationError) as exc:
                error=str(exc)
            else:return redirect("finance:recurring")
    return render(request,"finance/recurring.html",{"form":form,"error":error,
        "schedules":RecurringExpense.scoped(salon).order_by("next_due","pk"),"today":timezone.localdate()})
