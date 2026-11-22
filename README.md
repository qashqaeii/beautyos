# BeautyOS

پلتفرم SaaS مدیریت سالن‌های زیبایی (MVP در حال ساخت).

## پیش‌نیاز

- Python 3.11+
- Node.js 18+ (برای Tailwind)
- PostgreSQL 16 (توصیه production؛ بدون Docker از SQLite محلی استفاده می‌شود)

## راه‌اندازی سریع (Windows / توسعه)

```powershell
cd beautyos
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements/dev.txt
copy .env.example .env
npm install
npm run build:css
$env:DJANGO_SETTINGS_MODULE="config.settings.local"
python manage.py migrate
python manage.py seed_demo --scenario full
python manage.py seed_realistic_salon --reset   # professional sample data (slug: atiye-noor)
python manage.py runserver
```

### Superuser (مدیریت Django Admin)

ورود ادمین با **شماره موبایل** (نه username). ایمیل در مدل User ذخیره نمی‌شود.

```powershell
$env:BEAUTYOS_BOOTSTRAP_PASSWORD="your-secure-password"
python manage.py ensure_superuser --phone 09357930033 --name qashqaeii
```

یا بدون env، در ترمینال تعاملی از شما رمز می‌پرسد. رمز در repository ذخیره نمی‌شود.

ثبت‌نام در `/auth/register/` — کد OTP در **کنسول سرور** چاپ می‌شود (DevSMSProvider).

## Docker (PostgreSQL + Redis)

```bash
docker compose up -d db redis
# DATABASE_URL در .env را روی postgres تنظیم کنید
python manage.py migrate
```

## تست

```powershell
pytest
```

## ساختار

رجوع به `docs/MVP_PLAN.md` و پوشه `apps/`.

## وضعیت فازها

| فاز | وضعیت |
|-----|--------|
| PHASE 1 Foundation | تکمیل |
| PHASE 2 CRM | تکمیل (لیست، پروفایل، یادداشت، تگ، آرشیو) |
| PHASE 3–6 | MVP هسته (خدمات، کارکنان، نوبت، مالی، عمومی/رزرو، پیگیری) — نسخه اولیه |
| Sample data | `seed_realistic_salon --reset` — slug `atiye-noor`، ۱۲۰ مشتری، ۲۰ متخصص، ۳ ماه شمسی مالی (بدون برچسب دمو) |
| Demo (legacy) | `seed_demo` — slugs: `demo-salon-a`, `demo-barber-b` · فقط با `ALLOW_DEMO_SEED` |

## فاز ۶ — آماده‌سازی انتشار

راهنمای پیش‌انتشار، سلامت دیتابیس و تنظیمات محیط پروداکشن در [docs/QA_RELEASE_PHASE_6.md](docs/QA_RELEASE_PHASE_6.md) قرار دارد.
برای بررسی بدون تغییر دیتابیس یا ارسال پیامک، پس از اجرای Migration و collectstatic و تنظیم محیط Production، از `python manage.py release_check` استفاده کنید.
فایل `docker-compose.yml` فقط مخصوص توسعه محلی است، نه استقرار Production.
