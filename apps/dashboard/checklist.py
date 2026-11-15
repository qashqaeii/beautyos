from apps.appointments.models import Appointment
from apps.customers.models import Customer
from apps.salons.models import SalonInvitation
from apps.services.models import Service
from apps.staff.models import StaffProfile


def get_startup_checklist(salon):
    items = [
        {
            "id": "services",
            "label": "ثبت خدمات",
            "done": Service.scoped(salon).filter(is_deleted=False).exists(),
            "url_name": "services:create",
        },
        {
            "id": "staff",
            "label": "افزودن متخصص",
            "done": StaffProfile.scoped(salon).filter(is_deleted=False).exists(),
            "url_name": "staff:list",
        },
        {
            "id": "customer",
            "label": "ثبت اولین مشتری",
            "done": Customer.scoped(salon).filter(is_deleted=False).exists(),
            "url_name": "customers:create",
        },
        {
            "id": "appointment",
            "label": "ثبت اولین نوبت",
            "done": Appointment.scoped(salon).exists(),
            "url_name": "appointments:create",
        },
        {
            "id": "public",
            "label": "تکمیل صفحه عمومی",
            "done": bool(salon.tagline and salon.city),
            "url_name": "salons_settings:home",
        },
        {
            "id": "invite",
            "label": "دعوت منشی",
            "done": False,
            "url_name": "salons_members:home",
        },
    ]
    from apps.salons.models import SalonMembership

    items[5]["done"] = SalonInvitation.objects.filter(salon=salon).exists() or SalonMembership.objects.filter(
        salon=salon, role=SalonMembership.Role.RECEPTIONIST, is_active=True
    ).exists()
    done = sum(1 for i in items if i["done"])
    return {"items": items, "done_count": done, "total": len(items), "complete": done == len(items)}
