import pytest
from django.urls import reverse
from django.utils import timezone
from apps.expenses.models import Expense


@pytest.mark.django_db
def test_expense_modal_entry_and_save(client, owner_membership):
    client.force_login(owner_membership.user)
    response = client.get(reverse("expenses:create"), follow=True)
    assert response.status_code == 200
    assert response.context["expense_modal_open"]
    assert b'expense-create-form' in response.content
    invalid = client.post(reverse("expenses:create"), {"category":"other", "amount_toman":"0", "expense_date":timezone.localdate().isoformat()})
    assert invalid.status_code == 400
    assert invalid.context["expense_modal_open"]
    response = client.post(reverse("expenses:create"), {"category":"other", "amount_toman":"۱.۲۵۰.۰۰۰", "expense_date":timezone.localdate().isoformat(), "description":"test"})
    assert response.status_code == 302
    assert Expense.objects.filter(amount_toman=1250000, description="test").exists()


@pytest.mark.django_db
def test_expenses_search_keeps_month_totals(client, owner_membership, salon):
    client.force_login(owner_membership.user)
    today = timezone.localdate()
    Expense.objects.create(salon=salon, category="rent", amount_toman=1000, expense_date=today)
    Expense.objects.create(salon=salon, category="supplies", amount_toman=2000, expense_date=today)
    response = client.get(reverse("expenses:overview"), {"day": today.isoformat(), "q": "اجاره"})
    assert response.status_code == 200
    assert response.context["expense_total"] == 3000
    assert response.context["expense_page"].paginator.count == 1
    assert 'staff-board-search__submit' in response.content.decode()
    assert 'data-jalali-calendar-trigger' in response.content.decode()
