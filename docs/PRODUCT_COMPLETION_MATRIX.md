# BeautyOS — Product Completion Matrix

> آخرین به‌روزرسانی: ممیزی V3 (از کد و تست‌های `pytest`، نه صرفاً گزارش قبلی)

وضعیت‌ها: **Complete** · **Partial** · **Missing** · **Broken**

| حوزه | مدل | Views | Templates | URLs | Forms | Permissions | Tests | Nav | Mobile |
|------|-----|-------|-----------|------|-------|-------------|-------|-----|--------|
| Auth / OTP | Complete | Complete | Complete | Complete | Complete | Partial | Complete | — | Partial |
| Multi-Tenant | Complete | Complete | — | — | — | Partial | Complete | — | — |
| Onboarding Wizard | Complete | Complete | Partial | Complete | Complete | Partial | Partial | — | Partial |
| Theme Engine | Complete | Complete | Partial | — | Complete | Complete | Partial | — | — |
| Dashboard (Owner) | Partial | Complete | Partial | Complete | — | Partial | Partial | Complete | Partial |
| Reception Desk | Complete | Complete | Partial | Complete | — | Complete | Complete | Complete | Partial |
| Specialist Workday | Partial | Complete | Partial | Complete | — | Complete | Complete | Complete | Partial |
| CRM / Customers | Complete | Complete | Partial | Complete | Complete | Partial | Complete | Complete | Partial |
| Services | Complete | Complete | Partial | Complete | Complete | Partial | Partial | Complete | — |
| Staff | Complete | Partial | Partial | Complete | Partial | Partial | Missing | Complete | — |
| Staff Invitation | Complete | Complete | Partial | Complete | Complete | Complete | Partial | Complete | — |
| Appointments | Complete | Complete | Partial | Complete | Complete | Partial | Complete | Complete | Partial |
| Calendar | Complete | Complete | Partial | Complete | — | Partial | Complete | Complete | Partial |
| Finance / Payments | Complete | Complete | Partial | Complete | Complete | Partial | Partial | Complete | — |
| Commission | Complete | Complete | Partial | Complete | Complete | Partial | Partial | Complete | — |
| Expenses | Complete | Complete | Partial | Complete | Complete | Partial | Missing | Complete | — |
| Packages | Complete | Complete | Partial | Complete | Complete | Partial | Partial | Complete | — |
| Retention | Complete | Complete | Partial | Complete | — | Partial | Missing | Complete | — |
| Inventory | Complete | Partial | Partial | Complete | — | Complete | Missing | Partial | — |
| Loyalty | Complete | Partial | Partial | Complete | — | Complete | Missing | Partial | — |
| Waitlist | Complete | Partial | Partial | Complete | — | Complete | Missing | Partial | — |
| Public / Booking | Partial | Complete | Partial | Complete | Partial | Partial | Partial | — | Partial |
| Portfolio | Complete | Complete | Partial | Complete | Complete | Partial | Missing | Complete | — |
| Settings | Complete | Complete | Partial | Complete | Complete | Partial | Complete | Complete | — |
| RBAC (Granular) | Complete | Partial | — | — | — | Partial | Complete | Complete | — |
| First-Run Checklist | — | Complete | Partial | — | — | — | Missing | Partial | — |
| Audit Trail | Partial | Missing | — | — | — | — | Missing | — | — |

## یادداشت‌های کلیدی

- **Permissions:** نقش‌های `SalonMembership` + `require_role` گسترده است؛ ماتریس مجوز دقیق (V3) اضافه شد.
- **PostgreSQL:** تست migration/concurrency انجام نشده.
- **Inventory / Loyalty / Waitlist:** مدل و مسیرهای پایه V3؛ مصرف خودکار با نوبت در فاز بعد قابل اتصال است.

## Definition of Done (V3)

- [x] Reception Desk عملیاتی با داده واقعی (`/reception/`)
- [x] My Workday برای Specialist (`/my-workday/`)
- [x] دعوت عضویت + پذیرش با همان موبایل (`/members/`)
- [x] Sidebar براساس نقش
- [x] تست‌های دسترسی منفی RBAC (`tests/test_rbac.py`)
- [x] Checklist راه‌اندازی روی داشبورد مالک
- [ ] Checkout یکپارچه reception + رسید
- [ ] Audit روی رویدادهای مالی
- [ ] Public/booking + پکیج در جریان رزرو
- [ ] PostgreSQL concurrency
