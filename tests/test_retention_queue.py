import pytest
from django.urls import reverse

from apps.customers.models import Customer
from apps.retention.models import FollowUp


@pytest.mark.django_db
def test_retention_done_requires_note(client, salon, owner_membership):
    customer = Customer.objects.create(salon=salon, full_name="پیگیری تست", phone="+989121118881")
    item = FollowUp.objects.create(
        salon=salon,
        customer=customer,
        reason="۳۰ روز بدون مراجعه",
        days_since_visit=37,
        status=FollowUp.Status.OPEN,
    )
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()
    resp = client.post(reverse("retention:done", kwargs={"pk": item.pk}), {"result_note": "   "})
    assert resp.status_code == 302
    assert f"open={item.pk}" in resp.url
    item.refresh_from_db()
    assert item.status == FollowUp.Status.OPEN
    follow = client.get(resp.url)
    assert "نتیجه تماس" in follow.content.decode()


@pytest.mark.django_db
def test_retention_done_saves_and_removes_from_queue(client, salon, owner_membership):
    customer = Customer.objects.create(salon=salon, full_name="پیگیری دو", phone="+989121118882")
    item = FollowUp.objects.create(
        salon=salon,
        customer=customer,
        reason="۶۰ روز بدون مراجعه",
        days_since_visit=60,
        status=FollowUp.Status.OPEN,
    )
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()
    resp = client.post(
        reverse("retention:done", kwargs={"pk": item.pk}),
        {"result_note": "تماس گرفته شد"},
        follow=True,
    )
    assert resp.status_code == 200
    item.refresh_from_db()
    assert item.status == FollowUp.Status.DONE
    assert "پیگیری ثبت شد" in resp.content.decode()
    assert FollowUp.scoped(salon).filter(status=FollowUp.Status.OPEN, pk=item.pk).count() == 0
