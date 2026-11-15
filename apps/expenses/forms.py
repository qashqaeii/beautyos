from django import forms

from apps.core.forms import PersianModelForm
from apps.expenses.models import Expense


class ExpenseForm(PersianModelForm):
    class Meta:
        model = Expense
        fields = ["category", "amount_toman", "expense_date", "description"]
        widgets = {
            "category": forms.Select(attrs={"class": "input-field"}),
            "amount_toman": forms.NumberInput(attrs={"class": "input-field"}),
            "expense_date": forms.DateInput(attrs={"class": "input-field"}),
            "description": forms.TextInput(attrs={"class": "input-field"}),
        }
