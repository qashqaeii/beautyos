from django import forms

from apps.core.forms import PersianModelForm
from apps.portfolio.models import PortfolioItem


class PortfolioItemForm(PersianModelForm):
    class Meta:
        model = PortfolioItem
        fields = ["title", "description", "image", "category", "service", "sort_order", "is_published"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "input-field"}),
            "description": forms.Textarea(attrs={"class": "input-field", "rows": 2}),
            "category": forms.TextInput(attrs={"class": "input-field"}),
            "service": forms.Select(attrs={"class": "input-field"}),
            "sort_order": forms.NumberInput(attrs={"class": "input-field"}),
            "is_published": forms.CheckboxInput(attrs={"class": "rounded"}),
        }

    def __init__(self, *args, salon=None, **kwargs):
        super().__init__(*args, **kwargs)
        if salon:
            from apps.services.models import Service

            self.fields["service"].queryset = Service.scoped(salon).filter(is_deleted=False)
            self.fields["service"].required = False
