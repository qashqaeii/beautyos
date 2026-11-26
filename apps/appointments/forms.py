from datetime import datetime

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.core.fields import TomanAmountField
from apps.core.forms import PersianModelForm
from apps.finance.models import Payment
from apps.core.utils.phone import display_iran_mobile
from apps.core.widgets import JalaliDateWidget
from apps.customers.forms import CustomerCreateForm
from apps.customers.models import Customer, CustomerActivity
from apps.customers.search import find_customer_by_phone
from apps.customers.services import log_activity
from apps.salons.permissions_policy import P_CUSTOMER_CREATE, P_PAYMENT_CREATE, has_permission
from apps.services.models import Service
from apps.staff.fields import HHmmTimeField
from apps.staff.models import StaffProfile


def _combine_full_name(first: str, last: str) -> str:
    return f"{first.strip()} {last.strip()}".strip()


class ServiceStaffSelect(forms.Select):
    """Expose only active, salon-scoped service assignments for each option."""
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        staff = getattr(value, "instance", None)
        if staff is not None:
            option["attrs"]["data-service-ids"] = ",".join(
                str(pk) for pk in self.service_ids_by_staff.get(staff.pk, ())
            )
        return option


class AppointmentForm(PersianModelForm):
    customer_search = forms.CharField(
        label="جست‌وجوی مشتری",
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "input-field appt-customer-picker__input",
                "autocomplete": "off",
                "role": "combobox",
                "aria-autocomplete": "list",
            }
        ),
    )
    new_customer_mode = forms.BooleanField(required=False, widget=forms.HiddenInput)
    new_customer_first_name = forms.CharField(
        label="نام",
        required=False,
        max_length=60,
        widget=forms.TextInput(attrs={"class": "input-field", "autocomplete": "off"}),
    )
    new_customer_last_name = forms.CharField(
        label="نام خانوادگی",
        required=False,
        max_length=60,
        widget=forms.TextInput(attrs={"class": "input-field", "autocomplete": "off"}),
    )
    new_customer_phone = forms.CharField(
        label="شماره تماس",
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "input-field input-field--tel",
                "type": "tel",
                "inputmode": "tel",
                "dir": "ltr",
                "autocomplete": "tel",
            }
        ),
    )
    appointment_date = forms.DateField(
        label="تاریخ نوبت",
        widget=JalaliDateWidget(attrs={"class": "input-field"}),
    )
    appointment_time = HHmmTimeField(label="ساعت شروع")

    class Meta:
        model = Appointment
        fields = ["customer", "staff", "service", "notes", "status"]
        widgets = {
            "customer": forms.HiddenInput,
            "staff": forms.Select(attrs={"class": "input-field"}),
            "service": forms.Select(attrs={"class": "input-field"}),
            "notes": forms.Textarea(attrs={"class": "input-field", "rows": 3}),
            "status": forms.Select(attrs={"class": "input-field"}),
        }
        labels = {
            "staff": "متخصص",
            "service": "خدمت",
            "notes": "یادداشت",
            "status": "وضعیت",
        }

    def __init__(self, *args, salon=None, membership=None, locked_staff: StaffProfile | None = None, **kwargs):
        self.locked_staff = locked_staff
        super().__init__(*args, **kwargs)
        self.salon = salon
        self.membership = membership
        if salon:
            self.fields["customer"].queryset = Customer.scoped(salon).filter(is_deleted=False)
            staff_qs = StaffProfile.scoped(salon).filter(
                is_active=True, is_deleted=False, is_bookable=True
            )
            service_qs = Service.scoped(salon).filter(is_active=True, is_deleted=False)
            from apps.salons.models import SalonMembership
            if membership and membership.role == SalonMembership.Role.SPECIALIST:
                own_profile = getattr(membership, "staff_profile", None)
                staff_qs = staff_qs.filter(pk=own_profile.pk) if (
                    own_profile and own_profile.salon_id == salon.pk
                    and own_profile.is_active and not own_profile.is_deleted
                ) else staff_qs.none()
                # A forged staff preset must never bypass the authenticated identity.
                if self.locked_staff and not staff_qs.filter(pk=self.locked_staff.pk).exists():
                    self.locked_staff = None
            if self.locked_staff:
                self.fields["staff"].widget = forms.HiddenInput()
                self.fields["staff"].queryset = staff_qs.filter(pk=self.locked_staff.pk)
                service_qs = self.locked_staff.services.filter(
                    is_active=True, is_deleted=False, salon=salon
                )
                if not self.is_bound:
                    self.initial.setdefault("staff", self.locked_staff.pk)
            else:
                from collections import defaultdict
                assignments = defaultdict(list)
                for staff_id, service_id in staff_qs.filter(
                    services__in=service_qs
                ).values_list("pk", "services__pk"):
                    assignments[staff_id].append(service_id)
                staff_field = self.fields["staff"]
                staff_field.queryset = staff_qs.filter(pk__in=assignments)
                staff_field.widget = ServiceStaffSelect(attrs={"class": "input-field", "data-booking-staff-filter": "true"})
                staff_field.widget.service_ids_by_staff = assignments
                staff_field.empty_label = "ابتدا خدمت را انتخاب کنید"
                self.fields["staff"].label_from_instance = lambda obj: obj.full_display_name
            self.fields["service"].queryset = service_qs
            self.fields["service"].empty_label = "انتخاب خدمت"
        self.fields["customer"].required = False

        start_at = self.initial.get("start_at")
        if start_at and not self.is_bound:
            if isinstance(start_at, datetime):
                local_dt = timezone.localtime(start_at) if timezone.is_aware(start_at) else start_at
                self.initial.setdefault("appointment_date", local_dt.date())
                self.initial.setdefault("appointment_time", local_dt.time().replace(second=0, microsecond=0))

        self.allow_deposit = bool(membership and has_permission(membership, P_PAYMENT_CREATE))
        if self.allow_deposit:
            self.fields["deposit_amount_toman"] = TomanAmountField(
                label="مبلغ بیعانهٔ دریافتی",
                required=False,
                min_value=0,
            )
            self.fields["deposit_method"] = forms.ChoiceField(
                label="روش پرداخت",
                required=False,
                choices=Payment.Method.choices,
                widget=forms.Select(attrs={"class": "input-field"}),
            )

        customer = self.initial.get("customer") or (
            self.instance.customer_id if getattr(self.instance, "customer_id", None) else None
        )
        if customer and not self.is_bound:
            if isinstance(customer, Customer):
                self.initial.setdefault("customer", customer.pk)
                self.initial["customer_search"] = (
                    f"{customer.full_name} · {display_iran_mobile(customer.phone)}"
                )
            elif isinstance(customer, int) and salon:
                inst = Customer.scoped(salon).filter(pk=customer).first()
                if inst:
                    self.initial["customer_search"] = (
                        f"{inst.full_name} · {display_iran_mobile(inst.phone)}"
                    )

    def _clean_deposit(self, cleaned):
        if not getattr(self, "allow_deposit", False):
            raw = (self.data.get("deposit_amount_toman") or "").strip()
            if raw:
                raise ValidationError("مجوز ثبت بیعانه و ثبت پرداخت را ندارید.")
            return
        deposit = cleaned.get("deposit_amount_toman")
        if deposit is None:
            deposit = 0
        if deposit < 0:
            self.add_error("deposit_amount_toman", "مبلغ بیعانه نمی‌تواند منفی باشد.")
        service = cleaned.get("service")
        if service and deposit > service.price_toman:
            self.add_error(
                "deposit_amount_toman",
                "مبلغ بیعانه نمی‌تواند بیشتر از مبلغ نوبت باشد.",
            )
        if deposit > 0 and not cleaned.get("deposit_method"):
            self.add_error("deposit_method", "روش پرداخت را انتخاب کنید.")
        cleaned["deposit_amount_toman"] = deposit

    def clean_staff(self):
        staff = self.cleaned_data.get("staff")
        if not staff or not self.salon:
            return staff
        if staff.salon_id != self.salon.pk or staff.is_deleted or not staff.is_active or not staff.is_bookable:
            raise ValidationError("متخصص معتبر نیست.")
        if self.locked_staff and staff.pk != self.locked_staff.pk:
            raise ValidationError("متخصص قابل تغییر نیست.")
        from apps.salons.models import SalonMembership
        if self.membership and self.membership.role == SalonMembership.Role.SPECIALIST:
            own_profile = getattr(self.membership, "staff_profile", None)
            if not own_profile or own_profile.salon_id != self.salon.pk or staff.pk != own_profile.pk:
                raise ValidationError("فقط می‌توانید برای خودتان نوبت ثبت کنید.")
        return staff

    def clean(self):
        cleaned = super().clean()
        if self.locked_staff and self.salon:
            locked = (
                StaffProfile.scoped(self.salon)
                .filter(
                    pk=self.locked_staff.pk,
                    is_active=True,
                    is_deleted=False,
                    is_bookable=True,
                )
                .first()
            )
            if not locked:
                raise ValidationError("متخصص معتبر نیست.")
            cleaned["staff"] = locked
            self.locked_staff = locked
        staff = cleaned.get("staff")
        service = cleaned.get("service")
        if staff and service and not staff.services.filter(pk=service.pk).exists():
            self.add_error("staff", "متخصص انتخاب‌شده این خدمت را ارائه نمی‌دهد.")
        customer = cleaned.get("customer")
        new_mode = cleaned.get("new_customer_mode")
        first = (cleaned.get("new_customer_first_name") or "").strip()
        last = (cleaned.get("new_customer_last_name") or "").strip()
        phone_raw = (cleaned.get("new_customer_phone") or "").strip()
        appt_date = cleaned.get("appointment_date")
        appt_time = cleaned.get("appointment_time")

        if appt_date and appt_time is not None:
            tz = timezone.get_current_timezone()
            cleaned["start_at"] = timezone.make_aware(datetime.combine(appt_date, appt_time), tz)
        elif appt_date is None:
            self.add_error("appointment_date", "تاریخ نوبت را وارد کنید.")
        elif appt_time is None:
            self.add_error("appointment_time", "ساعت شروع را وارد کنید.")

        if customer:
            if customer.salon_id != self.salon.pk or customer.is_deleted:
                self.add_error("customer_search", "مشتری معتبر نیست.")
            self._clean_deposit(cleaned)
            return cleaned

        wants_new = bool(new_mode or first or last or phone_raw)
        if wants_new:
            if not has_permission(self.membership, P_CUSTOMER_CREATE):
                raise ValidationError("مجوز ثبت مشتری جدید را ندارید.")
            if not first:
                self.add_error("new_customer_first_name", "نام الزامی است.")
            if not last:
                self.add_error("new_customer_last_name", "نام خانوادگی الزامی است.")
            if not phone_raw:
                self.add_error("new_customer_phone", "شماره تماس الزامی است.")
            if self.errors:
                self._clean_deposit(cleaned)
                return cleaned

            full_name = _combine_full_name(first, last)
            create_form = CustomerCreateForm(
                data={
                    "full_name": full_name,
                    "phone_input": phone_raw,
                    "marketing_consent": False,
                },
                salon=self.salon,
            )
            if not create_form.is_valid():
                for field, errs in create_form.errors.items():
                    if field == "phone_input":
                        target = "new_customer_phone"
                    elif field == "full_name":
                        target = "new_customer_first_name"
                    else:
                        target = "new_customer_phone"
                    for err in errs:
                        self.add_error(target, err)
                self._clean_deposit(cleaned)
                return cleaned

            phone_e164 = create_form.cleaned_data["phone_input"]
            existing = find_customer_by_phone(self.salon, phone_e164)
            if existing:
                cleaned["customer"] = existing
                cleaned["customer_matched_existing"] = True
            else:
                cleaned["_new_customer_form"] = create_form
            self._clean_deposit(cleaned)
            return cleaned

        self.add_error(
            "customer_search",
            "مشتری را از فهرست انتخاب کنید."
            if not has_permission(self.membership, P_CUSTOMER_CREATE)
            else "مشتری را انتخاب کنید یا اطلاعات مشتری جدید را کامل کنید.",
        )
        self._clean_deposit(cleaned)
        return cleaned

    def resolve_customer(self, *, actor):
        if self.cleaned_data.get("customer"):
            return self.cleaned_data["customer"]
        create_form: CustomerCreateForm | None = self.cleaned_data.get("_new_customer_form")
        if not create_form:
            raise ValidationError("مشتری مشخص نیست.")
        customer = create_form.save()
        log_activity(
            salon=self.salon,
            customer=customer,
            activity_type=CustomerActivity.ActivityType.CREATED,
            title="مشتری از فرم نوبت ایجاد شد",
            actor=actor,
        )
        return customer
