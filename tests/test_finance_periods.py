from uuid import uuid4
import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from apps.core.utils.dates import jalali_month_bounds
from apps.expenses.models import Expense
from apps.finance.models import RecurringExpense, StaffPeriodPayment
from apps.finance.periods import create_agreement, open_staff_period, pay_staff_period, record_recurring_expense
from apps.staff.models import StaffProfile

@pytest.mark.django_db
def test_salary_advance_and_recurring(client,salon,owner_membership):
    staff,_=StaffProfile.objects.get_or_create(salon=salon,membership=owner_membership)
    today=timezone.localdate()
    actor=owner_membership.user
    create_agreement(salon=salon,staff_id=staff.pk,month=today,mode="hybrid",amount=1000000,actor=actor)
    row=open_staff_period(salon=salon,staff_id=staff.pk,month=today,actor=actor)
    assert open_staff_period(salon=salon,staff_id=staff.pk,month=today,actor=actor).pk==row.pk
    args=dict(salon=salon,period_id=row.pk,kind="advance",amount=300000,note="",request_key=uuid4(),actor=actor)
    pay=pay_staff_period(**args)
    assert pay_staff_period(**args).pk==pay.pk
    with pytest.raises(ValidationError): pay_staff_period(**{**args,"amount":800000,"request_key":uuid4()})
    assert StaffPeriodPayment.scoped(salon).count()==1
    schedule=RecurringExpense.objects.create(salon=salon,title="اجاره",category="rent",amount_toman=200000,next_due=today,day_of_month=1)
    first=record_recurring_expense(salon=salon,schedule_id=schedule.pk,expected_due=today,actor=actor)
    assert record_recurring_expense(salon=salon,schedule_id=schedule.pk,expected_due=today,actor=actor).pk==first.pk
    assert Expense.scoped(salon).count()==1
    schedule.refresh_from_db()
    assert schedule.next_due>today
    client.force_login(actor)
    assert client.get(reverse("finance:staff_finance")).status_code==200
    assert client.get(reverse("finance:recurring")).status_code==200
