import pytest

from apps.accounts.models import User
from apps.core.utils.phone import normalize_iran_mobile
from apps.salons.models import Salon, SalonMembership, SalonSettings


@pytest.fixture
def user(db):
    return User.objects.create_user(phone="+989121234567", full_name="کاربر تست")


@pytest.fixture
def salon(db):
    from django.utils import timezone

    s = Salon.objects.create(name="سالن آلفا", city="تهران")
    SalonSettings.objects.create(salon=s, onboarding_completed_at=timezone.now())
    return s


@pytest.fixture
def salon_b(db):
    from django.utils import timezone

    s = Salon.objects.create(name="سالن بتا", city="اصفهان")
    SalonSettings.objects.create(salon=s, onboarding_completed_at=timezone.now())
    return s


@pytest.fixture
def owner_membership(user, salon):
    return SalonMembership.objects.create(
        user=user,
        salon=salon,
        role=SalonMembership.Role.OWNER,
    )
