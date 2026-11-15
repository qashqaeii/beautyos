from apps.staff.models import StaffProfile


def staff_booking_label(staff: StaffProfile) -> str:
    """Label for booking UIs: full name, optional specialty in parentheses."""
    name = staff.full_display_name
    specialty = (staff.title or "").strip()
    if specialty:
        return f"{name} ({specialty})"
    return name
