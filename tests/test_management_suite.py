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


@pytest.mark.django_db
def test_staff_card_pagination_and_real_appointment_counts(client,salon,owner_membership):
    from datetime import timedelta
    from django.utils import timezone
    from apps.appointments.models import Appointment
    from apps.customers.models import Customer
    from apps.services.models import Service

    rows=[]
    for i in range(7):
        membership=owner_membership if i==0 else SalonMembership.objects.create(salon=salon,
            user=User.objects.create_user(phone=f"+98912123290{i}"),role=SalonMembership.Role.SPECIALIST)
        profile,_=StaffProfile.objects.get_or_create(salon=salon,membership=membership)
        profile.display_name=f"متخصص {i}"
        profile.save()
        rows.append(profile)
    service=Service.objects.create(salon=salon,name="رنگ مو",price_toman=200000)
    for profile in rows:
        profile.services.add(service)
    customer=Customer.objects.create(salon=salon,full_name="مشتری",phone="+989121232919")
    start=timezone.now()
    for offset,status in [(0,Appointment.Status.COMPLETED),(1,Appointment.Status.CANCELLED)]:
        a=start+timedelta(minutes=offset*10)
        Appointment.objects.create(salon=salon,customer=customer,staff=rows[0],service=service,start_at=a,
            end_at=a+timedelta(minutes=5),status=status,price_toman=200000)
    client.force_login(owner_membership.user)
    result=client.get(reverse("staff:list"),{"view":"card"})
    assert len(result.context["staff_list"])==6
    assert result.context["staff_page"].paginator.count==7
    assert result.context["directory_stats"]["services"]==1
    assert result.context["directory_stats"]["today"]==1
    assert result.context["staff_list"][0].month_count==1
    assert len(client.get(reverse("staff:list"),{"page":2}).context["staff_list"])==1
    table_first = client.get(reverse("staff:list"), {"view": "table"})
    table_second = client.get(reverse("staff:list"), {"view": "table", "page": 2})
    assert len(table_first.context["staff_list"]) == 6
    assert len(table_second.context["staff_list"]) == 1
    assert table_first.context["staff_page"].paginator.count == 7


@pytest.mark.django_db
def test_staff_reference_board_is_data_driven_and_accessible(client,salon,owner_membership):
    from apps.staff.models import StaffProfile
    from apps.services.models import Service
    profile,_=StaffProfile.objects.get_or_create(salon=salon,membership=owner_membership)
    service=Service.objects.create(salon=salon,name="کراتین",price_toman=1200000)
    profile.services.add(service)
    client.force_login(owner_membership.user)
    response=client.get(reverse("staff:list"))
    assert response.status_code==200
    markup=response.content.decode()
    assert 'staff-board-v2' in markup
    assert 'aria-label="جست‌وجوی متخصص"' in markup
    assert 'aria-label="وضعیت متخصص"' in markup
    assert 'aria-label="تخصص"' in markup
    assert markup.count('class="suite-kpi"')==4
    assert 'خدمت' in markup and 'نوبت امروز' in markup
    assert 'ساعات کاری' in markup and 'ویرایش' in markup
