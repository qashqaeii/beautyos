import pytest
from django.core.management import call_command
from django.urls import reverse

from apps.customers.models import Customer
from apps.loyalty.models import LoyaltyAccount, ledger_add_points, ledger_adjust_points
from apps.loyalty.tiers import tier_for_points
from apps.salons.models import Salon


@pytest.mark.django_db
def test_loyalty_overview_renders(client, salon, owner_membership):
    customer = Customer.objects.create(salon=salon, phone="+989121111111", full_name="مشتری باشگاه")
    ledger_add_points(salon=salon, customer=customer, points=120, note="خوش‌آمدگویی")
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()
    response = client.get(reverse("loyalty:overview"))
    assert response.status_code == 200
    content = response.content.decode()
    assert "باشگاه مشتریان" in content
    assert "مشتری باشگاه" in content
    assert "فعالیت اخیر" in content


@pytest.mark.django_db
def test_tier_for_points_and_adjust(salon):
    customer = Customer.objects.create(salon=salon, phone="+989121111112", full_name="سطح طلایی")
    ledger_add_points(salon=salon, customer=customer, points=250, note="تست")
    ledger_adjust_points(salon=salon, customer=customer, points_delta=300, note="هدیه")
    account = customer.loyalty
    account.refresh_from_db()
    assert tier_for_points(account.points_balance).key == "gold"


@pytest.mark.django_db
def test_loyalty_member_detail(client, salon, owner_membership):
    call_command("seed_demo", "--scenario=full", verbosity=0)
    demo_salon = Salon.objects.get(slug="demo-salon-a")
    account = LoyaltyAccount.scoped(demo_salon).select_related("customer").first()
    assert account is not None
    from apps.core.demo_seed.engine import OWNER_PHONES
    from apps.accounts.models import User

    owner = User.objects.get(phone=OWNER_PHONES["demo-salon-a"])
    client.force_login(owner)
    session = client.session
    session["active_salon_id"] = str(demo_salon.id)
    session.save()
    response = client.get(reverse("loyalty:member", kwargs={"pk": account.pk}))
    assert response.status_code == 200
    assert account.customer.full_name in response.content.decode()
