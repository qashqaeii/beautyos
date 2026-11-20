from django import forms
from django.contrib import messages
from django.db import transaction
from django.db.models import Count
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.audit.models import AuditLog
from apps.retention.automation import prepare_automation
from apps.retention.models import AutomationMessage,AutomationPolicy
from apps.salons.decorators import salon_required
from apps.salons.models import Salon,SalonSettings
from apps.salons.permissions_policy import P_MARKETING_MANAGE,require_permission


class AutomationForm(forms.Form):
    reminder_enabled=forms.BooleanField(label="یادآوری نوبت تأییدشده (۲۴ ساعت قبل)",required=False)
    birthday_enabled=forms.BooleanField(label="تبریک روز تولد شمسی",required=False)
    winback_enabled=forms.BooleanField(label="دعوت به مراجعه پس از ۶۰ روز",required=False)


@salon_required
@require_permission(P_MARKETING_MANAGE)
@require_http_methods(["GET","POST"])
def automation(request):
    salon=request.salon
    policy=AutomationPolicy.scoped(salon).first()
    values={key:getattr(policy,key,False) for key in AutomationForm.base_fields}
    action=request.POST.get("action")
    form=AutomationForm(request.POST if action=="save" else None,initial=values)
    if request.method=="POST":
        if action=="save" and form.is_valid():
            with transaction.atomic():
                Salon.objects.select_for_update(no_key=True).get(pk=salon.pk)
                row,_=AutomationPolicy.objects.get_or_create(salon=salon)
                for key,value in form.cleaned_data.items():setattr(row,key,value)
                row.save()
                AuditLog.objects.create(salon=salon,actor=request.user,action=AuditLog.Action.UPDATE,
                    entity_type="automation_policy",entity_id=str(row.pk),message="تنظیم اتوماسیون سالن",metadata=form.cleaned_data)
            messages.success(request,"تنظیمات ذخیره شد.")
            return redirect("retention:automation")
        if action=="prepare":
            count=prepare_automation(salon)
            messages.success(request,f"{count} پیام جدید آماده شد؛ هیچ پیامکی ارسال نشده است.")
            return redirect("retention:automation")
    qs=AutomationMessage.scoped(salon)
    counts={row["status"]:row["count"] for row in qs.values("status").annotate(count=Count("pk"))}
    return render(request,"retention/automation.html",{"form":form,"settings":SalonSettings.objects.filter(salon=salon).first(),
        "pending":counts.get("pending",0),"skipped":counts.get("skipped",0),"rows":qs.select_related("customer").order_by("-pk")[:60]})
