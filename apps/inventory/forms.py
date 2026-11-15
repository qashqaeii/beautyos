from django import forms
from django.core.exceptions import ValidationError

from apps.core.forms import PersianForm, PersianModelForm
from apps.inventory.models import InventoryCategory, InventoryItem

INVENTORY_CATEGORY_PRESETS = (
    "رنگ و دکلره",
    "مراقبت مو",
    "پوست",
    "ناخن",
    "مژه و ابرو",
    "لوازم مصرفی",
)


class InventoryCategoryForm(PersianModelForm):
    class Meta:
        model = InventoryCategory
        fields = ["name"]
        widgets = {"name": forms.TextInput(attrs={"class": "input-field", "autocomplete": "off"})}


class InventoryCategoryQuickForm(forms.Form):
    name = forms.CharField(max_length=80)

    def __init__(self, *args, salon=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.salon = salon

    def clean_name(self):
        name = (self.cleaned_data.get("name") or "").strip()
        if not name:
            raise ValidationError("نام دسته‌بندی را وارد کنید.")
        if (
            self.salon
            and InventoryCategory.objects.filter(salon=self.salon, name=name).exists()
        ):
            raise ValidationError("این نام دسته قبلاً ثبت شده است.")
        return name

    def save(self):
        return InventoryCategory.objects.create(salon=self.salon, name=self.cleaned_data["name"])


def inventory_category_queryset(salon):
    return InventoryCategory.objects.filter(salon=salon).order_by("name")


class InventoryItemCreateForm(PersianForm):
    inventory_product_name = forms.CharField(
        max_length=120,
        widget=forms.TextInput(
            attrs={
                "class": "input-field",
                "autocomplete": "off",
                "autocorrect": "off",
                "autocapitalize": "off",
                "spellcheck": "false",
            }
        ),
    )
    category = forms.ModelChoiceField(
        queryset=InventoryCategory.objects.none(),
        required=False,
        empty_label="بدون دسته‌بندی",
        widget=forms.Select(attrs={"class": "input-field"}),
    )
    unit = forms.ChoiceField(
        choices=InventoryItem.Unit.choices,
        initial=InventoryItem.Unit.PIECE,
        widget=forms.Select(attrs={"class": "input-field"}),
    )
    initial_quantity = forms.DecimalField(
        min_value=0,
        required=False,
        initial=0,
        widget=forms.NumberInput(attrs={"class": "input-field", "step": "any", "inputmode": "decimal"}),
    )
    minimum_quantity = forms.DecimalField(
        min_value=0,
        required=False,
        initial=0,
        widget=forms.NumberInput(attrs={"class": "input-field", "step": "any", "inputmode": "decimal"}),
    )

    def __init__(self, *args, salon=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.salon = salon
        self.fields["inventory_product_name"].label = "نام محصول"
        self.fields["category"].label = "دسته‌بندی"
        self.fields["unit"].label = "واحد"
        self.fields["initial_quantity"].label = "موجودی اولیه"
        self.fields["minimum_quantity"].label = "حداقل موجودی"
        if salon:
            self.fields["category"].queryset = inventory_category_queryset(salon)


class StockQuantityForm(forms.Form):
    quantity = forms.DecimalField(
        min_value=0.01,
        widget=forms.NumberInput(attrs={"class": "input-field", "step": "any", "inputmode": "decimal"}),
    )
    note = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "input-field", "autocomplete": "off"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["quantity"].label = "مقدار"
        self.fields["note"].label = "توضیحات (اختیاری)"
