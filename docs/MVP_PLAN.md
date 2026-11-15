# BeautyOS — برنامه MVP و معماری

## ۱. تعریف MVP

ورود OTP موبایل، ساخت Workspace سالن، جداسازی Tenant، داشبورد KPI واقعی (جایی که مدل آماده است)، CRM مشتری، خدمات، کارکنان، نوبت با جلوگیری از تداخل، مالی پایه، صفحه عمومی + رزرو آنلاین، گالری، پیگیری مشتریان، تنظیمات، Responsive، Seed، تست‌های هسته.

## ۲. معماری

**Modular Monolith** (Django 5.1): یک deploy، اپ‌های دامنه‌ای جدا، سرویس‌محور برای منطق تجاری، DRF Session-ready برای موبایل آینده. **Shared DB + Application-level Tenant** با `salon_id` روی همه موجودیت‌های تجاری و Middleware برای `request.salon`.

## ۳. موجودیت‌های اصلی DB (خلاصه)

| موجودیت | نقش |
|---------|-----|
| User | احراز هویت (phone) |
| OTPChallenge | OTP |
| Salon / SalonSettings / SalonMembership | Tenant و نقش |
| Customer (+ آینده: Note, Activity, Tag) | CRM |
| Service / ServiceCategory | خدمات |
| Staff / Schedule | کارکنان |
| Appointment | نوبت |
| Payment | مالی |
| PortfolioItem | گالری |
| Notification | اعلان |
| AuditLog | Audit |

## ۴. نقشه صفحات

`auth/*` → onboarding → `dashboard` | `customers/*` | `appointments/*` | `settings` | عمومی `/s/{slug}/` → booking wizard.

## ۵. Design System

Tailwind + توکن‌های Aubergine/Lavender/Champagne/Ivory، Vazirmatn، RTL، سه تم عمومی صفحه سالن.

## ۶. فازها

0 معماری · 1 Foundation (فعلی) · 2 CRM · 3 Appointments · 4 Dashboard/Finance/Retention · 5 Public/Booking · 6 QA/Release.

## ۷. ریسک‌ها

جداسازی Tenant، Race Condition نوبت، OTP/SMS، تقویم شمسی، Performance لیست‌ها — با تست و PostgreSQL constraints.
