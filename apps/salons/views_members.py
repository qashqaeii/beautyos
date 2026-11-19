from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.salons.decorators import salon_required
from apps.salons.forms_members import InviteMemberForm
from apps.salons import invitations
from apps.salons.models import SalonInvitation, SalonMembership
from apps.salons.permissions_policy import require_permission, P_MEMBERS_MANAGE


@salon_required
@require_permission(P_MEMBERS_MANAGE)
def members_home(request):
    pending = SalonInvitation.objects.filter(salon=request.salon, status=SalonInvitation.Status.PENDING)
    members = SalonMembership.objects.filter(salon=request.salon, is_active=True).select_related("user")
    return render(
        request,
        "salons/members.html",
        {"pending_invites": pending, "members": members, "invite_form": InviteMemberForm()},
    )


@salon_required
@require_permission(P_MEMBERS_MANAGE)
def invite_create(request):
    form = InviteMemberForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            invitations.create_invitation(
                salon=request.salon,
                inviter=request.user,
                phone=form.cleaned_data["phone"],
                role=form.cleaned_data["role"],
            )
            messages.success(request, "دعوت‌نامه ایجاد شد.")
        except ValueError as exc:
            messages.error(request, str(exc))
    return redirect("salons_members:home")


@salon_required
@require_permission(P_MEMBERS_MANAGE)
def invite_cancel(request, pk):
    invite = get_object_or_404(SalonInvitation, pk=pk, salon=request.salon, status=SalonInvitation.Status.PENDING)
    invite.status = SalonInvitation.Status.CANCELLED
    invite.save(update_fields=["status", "updated_at"])
    messages.success(request, "دعوت لغو شد.")
    return redirect("salons_members:home")


@salon_required
@require_permission(P_MEMBERS_MANAGE)
def toggle_staff_manage(request, pk):
    membership = get_object_or_404(SalonMembership, pk=pk, salon=request.salon, is_active=True)
    if membership.role != SalonMembership.Role.RECEPTIONIST:
        messages.error(request, "فقط برای منشی قابل تنظیم است.")
        return redirect("salons_members:home")
    membership.can_manage_staff = not membership.can_manage_staff
    membership.save(update_fields=["can_manage_staff", "updated_at"])
    label = "فعال" if membership.can_manage_staff else "غیرفعال"
    messages.success(request, f"مدیریت متخصص‌ها برای این منشی {label} شد.")
    return redirect("salons_members:home")


@login_required
def accept_invite(request, token):
    from apps.salons.invitations import accept_invitation

    try:
        membership = accept_invitation(token, request.user)
        request.session["active_salon_id"] = str(membership.salon_id)
        request.session["explicit_salon_id"] = str(membership.salon_id)
        messages.success(request, f"به سالن {membership.salon.name} پیوستید.")
        return redirect("dashboard:home")
    except (SalonInvitation.DoesNotExist, ValueError) as exc:
        messages.error(request, str(exc) if str(exc) else "دعوت معتبر نیست.")
        return redirect("dashboard:home")
