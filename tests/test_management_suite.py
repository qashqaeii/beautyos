import pytest
from django.urls import reverse
from apps.staff.models import StaffProfile
from apps.accounts.models import User
from apps.salons.models import SalonMembership

@pytest.mark.django_db
def test_staff_directory_filters_and_isolation(client,salon,salon_b,owner_membership):
    member=owner_membership
    profile,_=StaffProfile.objects.get_or_create(salon=salon,membership=member)
    profile.display_name="متخصص تست ویژه"
    profile.title="رنگ"
    profile.save()
    outsider=User.objects.create_user(phone="+989121232991")
    foreign=SalonMembership.objects.create(salon=salon_b,user=outsider,role=SalonMembership.Role.SPECIALIST)
    StaffProfile.objects.create(salon=salon_b,membership=foreign,display_name="متخصص تست خارجی",title="رنگ")
    client.force_login(member.user)
    response=client.get(reverse("staff:list"),{"q":"تست"})
    assert response.status_code==200
    assert list(response.context["staff_list"])==[profile]
    assert response.context["directory_stats"]["total"]==1
    assert "management-suite" in response.content.decode()
    profile.is_active=False
    profile.save()
    assert not client.get(reverse("staff:list"),{"status":"bookable"}).context["staff_list"]
    assert list(client.get(reverse("staff:list"),{"status":"inactive"}).context["staff_list"])==[profile]
    finance=client.get(reverse("finance:overview"))
    assert "beautyos-main-bg__shell management-suite" not in finance.content.decode()
