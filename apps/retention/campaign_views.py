from datetime import datetime
from uuid import uuid4
import jdatetime

from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.retention.campaigns import cancel_campaign,create_campaign,eligible_members,marketing_enabled,prepare_campaign,schedule_campaign
from apps.retention.models import Campaign,AutomationMessage
from apps.retention.transport import ready
from apps.salons.decorators import salon_required
from apps.salons.permissions_policy import P_MARKETING_MANAGE,require_permission


class CampaignForm(forms.Form):
    title=forms.CharField(max_length=100,label="نام کمپین")
    segment=forms.ChoiceField(choices=Campaign.Segment.choices,label="گروه مخاطبان")
    message=forms.CharField(max_length=480,label="متن پیام",widget=forms.Textarea(attrs={"rows":3,"placeholder":"{name} عزیز، ..."}))
    request_key=forms.UUIDField(widget=forms.HiddenInput)
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        for field in self.visible_fields():field.field.widget.attrs["class"]="input-field"


def parse_campaign_time(value):
    """Parse optional Jalali date/time in Tehran local timezone."""
    value=(value or "").strip().translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩","01234567890123456789"))
    if not value:
        return timezone.now()
    try:
        date_part,time_part=value.split()
        year,month,day=map(int,date_part.split("/"))
        hour,minute=map(int,time_part.split(":"))
        if not (0<=hour<=23 and 0<=minute<=59):
            raise ValueError
        gregorian=jdatetime.date(year,month,day).togregorian()
        return timezone.make_aware(datetime(gregorian.year,gregorian.month,gregorian.day,hour,minute))
    except (TypeError,ValueError,OverflowError):
        raise ValidationError("تاریخ را به صورت ۱۴۰۵/۰۹/۰۱ ۱۰:۳۰ وارد کنید.") from None


@salon_required
@require_permission(P_MARKETING_MANAGE)
@require_http_methods(["GET","POST"])
def campaigns(request):
    salon=request.salon
    form=CampaignForm(request.POST if request.method=="POST" else None,initial={"request_key":uuid4()})
    if request.method=="POST" and form.is_valid():
        try:row=create_campaign(salon=salon,actor=request.user,**form.cleaned_data)
        except ValidationError as exc:form.add_error(None,exc)
        else:return redirect("retention:campaign_detail",pk=row.pk)
    segments=[{"label":label,"eligible":eligible_members(salon,key).count()} for key,label in Campaign.Segment.choices]
    rows=Campaign.scoped(salon).annotate(recipient_count=Count("recipients")).order_by("-pk")[:50]
    return render(request,"retention/campaigns.html",{"form":form,"rows":rows,"segments":segments,"enabled":marketing_enabled(salon)})


@salon_required
@require_permission(P_MARKETING_MANAGE)
@require_http_methods(["GET","POST"])
def campaign_detail(request,pk):
    row=get_object_or_404(Campaign.scoped(request.salon),pk=pk)
    if request.method=="POST":
        action=request.POST.get("action")
        try:
            if action=="prepare":prepare_campaign(salon=request.salon,campaign_id=pk,actor=request.user)
            elif action=="schedule":schedule_campaign(salon=request.salon,campaign_id=pk,scheduled_at=parse_campaign_time(request.POST.get("scheduled_at")),actor=request.user)
            elif action=="cancel":cancel_campaign(salon=request.salon,campaign_id=pk,actor=request.user)
            else:raise ValidationError("عملیات معتبر نیست.")
        except ValidationError as exc:messages.error(request,str(exc))
        return redirect("retention:campaign_detail",pk=pk)
    recipients=row.recipients.filter(salon=request.salon,customer__salon=request.salon)
    delivery=AutomationMessage.scoped(request.salon).filter(campaign_recipient__campaign=row)
    delivery_counts={r["status"]:r["count"] for r in delivery.values("status").annotate(count=Count("pk"))}
    return render(request,"retention/campaign_detail.html",{"campaign":row,"eligible":eligible_members(request.salon,row.segment).count(),"enabled":marketing_enabled(request.salon),"transport_ready":ready(),"delivery_counts":delivery_counts,
        "count":recipients.count(),"current_consent_count":recipients.filter(customer__marketing_consent=True,customer__is_deleted=False).exclude(customer__phone="").count(),
        "recipients":recipients.select_related("customer").order_by("pk")[:100]})
