import secrets
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.core.utils.phone import normalize_iran_mobile
from apps.salons.models import Salon, SalonInvitation, SalonMembership


def _active_owner_count(salon: Salon) -> int:
    return SalonMembership.objects.filter(
        salon=salon, role=SalonMembership.Role.OWNER, is_active=True
    ).count()


@transaction.atomic
def create_invitation(
    *,
    salon,
    inviter,
    phone: str,
    role: str,
    invitee_first_name: str = "",
    invitee_last_name: str = "",
    invitee_specialty: str = "",
) -> SalonInvitation:
    phone = normalize_iran_mobile(phone)
    if SalonMembership.objects.filter(salon=salon, user__phone=phone, is_active=True).exists():
        raise ValueError("این کاربر از قبل عضو سالن است.")
    if SalonInvitation.objects.filter(salon=salon, phone=phone, status=SalonInvitation.Status.PENDING).exists():
        raise ValueError("دعوت‌نامه باز برای این شماره وجود دارد.")
    if role == SalonMembership.Role.OWNER and _active_owner_count(salon) == 0:
        pass
    return SalonInvitation.objects.create(
        salon=salon,
        phone=phone,
        role=role,
        invitee_first_name=(invitee_first_name or "").strip(),
        invitee_last_name=(invitee_last_name or "").strip(),
        invitee_specialty=(invitee_specialty or "").strip(),
        invited_by=inviter,
        token=secrets.token_urlsafe(32),
        expires_at=timezone.now() + timedelta(days=7),
    )


@transaction.atomic
def accept_invitation(token: str, user: User) -> SalonMembership:
    invite = SalonInvitation.objects.select_for_update().select_related("salon").get(token=token)
    if invite.status != SalonInvitation.Status.PENDING:
        raise ValueError("دعوت‌نامه معتبر نیست.")
    if invite.expires_at < timezone.now():
        raise ValueError("دعوت‌نامه منقضی شده است.")
    if user.phone != invite.phone:
        raise ValueError("این دعوت برای شماره دیگری است.")
    membership, created = SalonMembership.objects.get_or_create(
        user=user,
        salon=invite.salon,
        defaults={"role": invite.role, "is_active": True},
    )
    if not created:
        membership.role = invite.role
        membership.is_active = True
        membership.save(update_fields=["role", "is_active", "updated_at"])
    invite.status = SalonInvitation.Status.ACCEPTED
    invite.save(update_fields=["status", "updated_at"])

    if invite.role == SalonMembership.Role.SPECIALIST:
        _ensure_specialist_profile_from_invite(invite, membership)

    return membership


def _ensure_specialist_profile_from_invite(invite: SalonInvitation, membership: SalonMembership) -> None:
    from apps.staff.models import StaffProfile

    display = " ".join(
        part for part in (invite.invitee_first_name, invite.invitee_last_name) if part
    ).strip()
    profile, created = StaffProfile.objects.get_or_create(
        membership=membership,
        defaults={
            "salon": invite.salon,
            "display_name": display,
            "title": invite.invitee_specialty or "",
        },
    )
    if created:
        return
    update_fields = []
    if display and not profile.display_name:
        profile.display_name = display
        update_fields.append("display_name")
    if invite.invitee_specialty and not profile.title:
        profile.title = invite.invitee_specialty
        update_fields.append("title")
    if update_fields:
        update_fields.append("updated_at")
        profile.save(update_fields=update_fields)


@transaction.atomic
def deactivate_member(membership: SalonMembership) -> None:
    if membership.role == SalonMembership.Role.OWNER and _active_owner_count(membership.salon) <= 1:
        raise ValueError("امکان غیرفعال‌کردن آخرین مالک نیست.")
    membership.is_active = False
    membership.save(update_fields=["is_active", "updated_at"])
