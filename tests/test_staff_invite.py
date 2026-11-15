import pytest
from django.contrib.auth import get_user_model

from apps.salons import invitations
from apps.salons.models import SalonMembership
from apps.staff.models import StaffProfile

UserModel = get_user_model()


@pytest.mark.django_db
def test_staff_invite_creates_profile_on_accept(salon, owner_membership):
    owner = owner_membership.user
    phone = "+989121009988"
    invitee = UserModel.objects.create_user(phone=phone, full_name="")
    inv = invitations.create_invitation(
        salon=salon,
        inviter=owner,
        phone=phone,
        role=SalonMembership.Role.SPECIALIST,
        invitee_first_name="سارا",
        invitee_last_name="احمدی",
        invitee_specialty="رنگ و لایت",
    )
    membership = invitations.accept_invitation(inv.token, invitee)
    profile = StaffProfile.objects.get(membership=membership)
    assert profile.display_name == "سارا احمدی"
    assert profile.title == "رنگ و لایت"
    assert profile.salon_id == salon.pk


@pytest.mark.django_db
def test_legacy_invite_without_names_still_accepts(salon, owner_membership):
    owner = owner_membership.user
    phone = "+989121009989"
    invitee = UserModel.objects.create_user(phone=phone, full_name="قدیمی")
    inv = invitations.create_invitation(
        salon=salon,
        inviter=owner,
        phone=phone,
        role=SalonMembership.Role.SPECIALIST,
    )
    membership = invitations.accept_invitation(inv.token, invitee)
    assert membership.role == SalonMembership.Role.SPECIALIST
    profile = StaffProfile.objects.get(membership=membership)
    assert profile.display_name == ""
