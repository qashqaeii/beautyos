import pytest

from apps.accounts.models import User
from apps.salons.models import SalonMembership


@pytest.mark.django_db
def test_receptionist_cannot_access_expenses(client, salon, owner_membership):
    receptionist = User.objects.create_user(phone="+989121234560", full_name="منشی")
    SalonMembership.objects.create(user=receptionist, salon=salon, role=SalonMembership.Role.RECEPTIONIST, is_active=True)
    client.force_login(receptionist)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()
    response = client.get("/expenses/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_receptionist_can_access_reception_desk(client, salon, owner_membership):
    receptionist = User.objects.create_user(phone="+989121234561", full_name="منشی")
    SalonMembership.objects.create(user=receptionist, salon=salon, role=SalonMembership.Role.RECEPTIONIST, is_active=True)
    client.force_login(receptionist)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()
    response = client.get("/reception/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_specialist_cannot_access_commission_rules(client, salon, owner_membership):
    specialist = User.objects.create_user(phone="+989121234562", full_name="متخصص")
    SalonMembership.objects.create(user=specialist, salon=salon, role=SalonMembership.Role.SPECIALIST, is_active=True)
    client.force_login(specialist)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()
    response = client.get("/commissions/rules/")
    assert response.status_code == 403
