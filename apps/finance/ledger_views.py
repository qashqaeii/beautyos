from uuid import uuid4

from django import forms
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.audit.models import AuditLog
from apps.commissions.models import CommissionSettlement
from apps.core.forms import PersianForm
from apps.expenses.models import Expense
from apps.finance.ledger import MAX_MONEY, account_balance, payment_refunded, post_movement, refund_payment
from apps.finance.models import AccountMovement, FinancialAccount, Payment, Refund, SalonDebtPayment
from apps.packages.models import CustomerPackage
from apps.salons.decorators import salon_required
from apps.salons.permissions_policy import P_FINANCE_REPORTS, require_permission


class StyledForm(PersianForm):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        for field in self.visible_fields():
            field.field.widget.attrs["class"]="input-field"


class AccountForm(StyledForm):
    name=forms.CharField(max_length=100,label="نام حساب")
    kind=forms.ChoiceField(choices=[("cash","صندوق نقدی"),("bank","حساب بانکی")],label="نوع حساب")
    opening_toman=forms.IntegerField(min_value=0,max_value=MAX_MONEY,label="موجودی ابتدای دوره (تومان)")
    opening_day=forms.DateField(label="تاریخ شروع ثبت",initial=timezone.localdate)


class MovementForm(StyledForm):
    request_key=forms.UUIDField(widget=forms.HiddenInput)
    kind=forms.ChoiceField(label="نوع گردش",choices=[("transfer","انتقال بین حساب‌ها"),("other_in","سایر ورود وجه"),("other_out","سایر خروج وجه")])
    from_account=forms.ModelChoiceField(queryset=FinancialAccount.objects.none(),required=False,label="از حساب")
    to_account=forms.ModelChoiceField(queryset=FinancialAccount.objects.none(),required=False,label="به حساب")
    amount=forms.IntegerField(min_value=1,max_value=MAX_MONEY,label="مبلغ (تومان)")
    note=forms.CharField(required=False,max_length=255,label="توضیح")
    def __init__(self,*args,salon,**kwargs):
        super().__init__(*args,**kwargs)
        for key in ("from_account","to_account"):
            self.fields[key].queryset=FinancialAccount.scoped(salon).order_by("name")
            self.fields[key].label_from_instance=lambda obj: obj.name


class PostingForm(StyledForm):
    request_key=forms.UUIDField(widget=forms.HiddenInput)
    event=forms.ChoiceField(label="سند ثبت‌شده")
    account=forms.ModelChoiceField(queryset=FinancialAccount.objects.none(),label="حساب")
    def __init__(self,*args,salon,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields["account"].queryset=FinancialAccount.scoped(salon).order_by("name")
        self.fields["account"].label_from_instance=lambda obj: obj.name
        sources=[("payment",Payment.scoped(salon).filter(paid_amount_toman__gt=0).exclude(status=Payment.Status.REFUNDED),"دریافت مشتری","paid_amount_toman",True),
          ("refund",Refund.scoped(salon),"استرداد","amount_toman",False),
          ("expense",Expense.scoped(salon).filter(amount_toman__gt=0),"هزینه","amount_toman",False),
          ("commission",CommissionSettlement.scoped(salon),"تسویه متخصص","amount_toman",False),
          ("debt",SalonDebtPayment.scoped(salon),"پرداخت بدهی","amount_toman",False),
          ("package",CustomerPackage.scoped(salon).filter(price_paid_toman__gt=0),"فروش پکیج","price_paid_toman",True)]
        self.directions={}
        choices=[]
        for key,qs,label,field,inbound in sources:
            posted=AccountMovement.scoped(salon).filter(source_kind=key,source_id__isnull=False).values("source_id")
            for obj in qs.exclude(pk__in=posted).order_by("-created_at","-pk")[:30]:
                val=f"{key}:{obj.pk}"
                choices.append((val,f"{label} #{obj.pk} — {getattr(obj,field):,} تومان"))
                self.directions[val]=inbound
        # Bound retries may refer to a just-posted document. The service revalidates the source.
        if self.is_bound:
            event=self.data.get("event","")
            if event not in self.directions:
                try:
                    kind,pk=event.split(":")
                    if kind in {s[0] for s in sources} and 0<int(pk)<=MAX_MONEY:
                        choices.append((event,event))
                        self.directions[event]=kind in ("payment","package")
                except (ValueError,TypeError):
                    pass
        self.fields["event"].choices=choices


class RefundForm(StyledForm):
    request_key=forms.UUIDField(widget=forms.HiddenInput)
    amount=forms.IntegerField(min_value=1,max_value=MAX_MONEY,label="مبلغ استرداد (تومان)")
    reason=forms.CharField(max_length=255,label="علت استرداد")


@salon_required
@require_permission(P_FINANCE_REPORTS)
@require_http_methods(["GET","POST"])
def accounts_view(request):
    salon=request.salon
    action=request.POST.get("action")
    account_form=AccountForm(request.POST if action=="account" else None)
    movement=MovementForm(request.POST if action=="movement" else None,salon=salon,initial={"request_key":uuid4()})
    posting=PostingForm(request.POST if action=="posting" else None,salon=salon,initial={"request_key":uuid4()})
    if request.method=="POST":
        if action=="account" and account_form.is_valid():
            d=account_form.cleaned_data
            if d["opening_day"]>timezone.localdate():
                account_form.add_error("opening_day","تاریخ شروع نباید در آینده باشد.")
            else:
                try:
                    with transaction.atomic():
                        row=FinancialAccount.objects.create(salon=salon,**d)
                        AuditLog.objects.create(salon=salon,actor=request.user,action=AuditLog.Action.CREATE,
                            entity_type="financial_account",entity_id=str(row.pk),message="ایجاد حساب مالی")
                except IntegrityError:
                    account_form.add_error("name","این نام حساب قبلاً ثبت شده است.")
                else:
                    return redirect("finance:accounts")
        if action=="movement" and movement.is_valid():
            d=movement.cleaned_data
            try:
                post_movement(salon=salon,kind=d["kind"],from_id=d["from_account"].pk if d["from_account"] else None,
                    to_id=d["to_account"].pk if d["to_account"] else None,amount=d["amount"],note=d["note"],request_key=d["request_key"],actor=request.user)
            except ValidationError as exc:
                movement.add_error(None,exc)
            else:
                return redirect("finance:accounts")
        if action=="posting" and posting.is_valid():
            d=posting.cleaned_data
            kind,pk=d["event"].split(":")
            inbound=posting.directions[d["event"]]
            try:
                post_movement(salon=salon,kind=kind,source_id=int(pk),to_id=d["account"].pk if inbound else None,
                    from_id=None if inbound else d["account"].pk,request_key=d["request_key"],actor=request.user)
            except ValidationError as exc:
                posting.add_error(None,exc)
            else:
                return redirect("finance:accounts")
    accounts=[{"account":row,"balance":account_balance(row)} for row in FinancialAccount.scoped(salon).order_by("name")]
    return render(request,"finance/accounts.html",{"accounts":accounts,"account_form":account_form,
        "movement_form":movement,"posting_form":posting,"movements":AccountMovement.scoped(salon).select_related("from_account","to_account").order_by("-day","-pk")[:50]})


@salon_required
@require_permission(P_FINANCE_REPORTS)
@require_http_methods(["GET","POST"])
def refund_view(request,payment_id):
    payment=get_object_or_404(Payment.scoped(request.salon).select_related("customer"),pk=payment_id)
    form=RefundForm(request.POST if request.method=="POST" else None,initial={"request_key":uuid4()})
    if request.method=="POST" and form.is_valid():
        try:
            refund_payment(salon=request.salon,payment_id=payment.pk,amount=form.cleaned_data["amount"],
                reason=form.cleaned_data["reason"],request_key=form.cleaned_data["request_key"],actor=request.user)
        except ValidationError as exc:
            form.add_error(None,exc)
        else:
            return redirect("finance:receipt",payment_id=payment.pk)
    return render(request,"finance/refund.html",{"payment":payment,"form":form,
        "available":max(0,payment.paid_amount_toman-payment_refunded(payment)) if payment.status!=Payment.Status.REFUNDED else 0})
