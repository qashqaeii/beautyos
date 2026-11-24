# BeautyOS — فاز ۸: آمادگی انتشار کنترل‌شده (بدون دیپلوی)

## محدوده فعلی
- تنظیمات امن Production، PostgreSQL، OTP واقعی و endpointهای health/readiness از فازهای قبلی موجود بوده‌اند.
- کنترل مستقل جدید در `release_check`: دامنه‌های صریح (بدون wildcard)، CSRF trusted origins حتماً HTTPS، ریدایرکت HTTPS و کوکی‌های امن.
- ابزار فقط خواندنی `python scripts/staging_smoke.py --base-url https://STAGING-DOMAIN`، بررسی دو endpoint سلامت، خروجی غیرصفر در صورت خطا.
- تست‌های امنیت و رفتار ابزار بدون نیاز به سرور واقعی.
- **این تغییرات هیچ دیتابیس واقعی را تغییر نمی‌دهند و Production را دیپلوی نمی‌کنند.**

## پیش‌نیازهای زیرساخت (باید توسط اپراتور تأیید شوند)

- دامنه مجزای Staging و گواهی TLS معتبر، DNS و reverse proxy با کنترل دقیق هدرهای forwarding. مقدار `BEAUTYOS_TRUST_PROXY_SSL_HEADER=True` فقط در صورت پاک‌سازی و بازنویسی `X-Forwarded-Proto` توسط reverse proxy اختصاصی.
- سرویس اپلیکیشن و worker با کاربر غیراصلی سیستم و تنظیم راه‌اندازی مجدد، timeout و لاگ مرکزی.
- PostgreSQL با TLS در صورت اتصال از شبکه، نقش و رمز مجزا، backup retention و اتصال محدود شبکه.
- Persistent media storage جدا از Docker image و نسخه پشتیبان مستقل از دیتابیس.
- Secret manager یا environment محافظت‌شده؛ هرگز رمز، API key و dump دیتابیس در Git نگهداری نشود.
- `BEAUTYOS_AUTOMATION_SEND_ENABLED=False` تا بررسی صریح ارسال واقعی انجام شود.
- هیچ Seed دمو یا ارسال OTP تستی روی اطلاعات واقعی.

## اجرای ایمن آماده‌سازی در Staging

1. آخرین کامیت تأییدشده را انتخاب و SHA و تنظیمات انتشار را ثبت کنید.
2. دیتابیس و media محیط آزمایشی *ایزوله* را تهیه کنید؛ از اطلاعات مشتریان واقعی برای تست بدون مجوز و ماسک کردن استفاده نکنید.
3. به‌صورت ایمن مقدار `DJANGO_SETTINGS_MODULE=config.settings.production`، `DATABASE_URL` و Secrets را تزریق کنید.
4. قبل از ترافیک، `python manage.py check --deploy`، `python manage.py migrate --noinput`، `python manage.py collectstatic --noinput` و `python manage.py release_check` اجرا شوند.
5. ابزار `python scripts/staging_smoke.py --base-url https://STAGING-DOMAIN` با هر دو خروجی PASS بررسی شود.
6. تست دستی OTP با شماره مجاز، ثبت‌نام سالن، نقش‌ها، تقویم و جلوگیری از نوبت تکراری، پذیرش و فاکتور، رزرو مشتری، ویرایش اطلاعات، لغو و بازپرداخت را روی Staging اجرا کنید.
7. تا زمان تأیید Restore و Rollback و مانیتورینگ، ترافیک واقعی به محیط جدید هدایت نشود.

## بکاپ و بازیابی (روش عملیاتی پیشنهادی)

این مثال‌ها باید **توسط اپراتور روی محیط ایزوله** و با دسترسی محرمانه به اتصال PostgreSQL اجرا شوند. خروجی شامل داده حساس است؛ مسیر نسخه پشتیبان باید رمزنگاری و با دسترسی محدود باشد.

- بکاپ: `pg_dump --format=custom --no-owner --no-acl --file=/secure-backups/beautyos-staging.dump "$STAGING_DATABASE_URL"`
- رسانه‌ها: ابزار ذخیره‌سازی مطمئن با snapshot/versioning و نگهداری خارج از میزبان؛ هماهنگی زمانی با dump ضروری است.
- **بازیابی تنها روی دیتابیس ایزوله و خالی** با نام مجزا: `pg_restore --no-owner --no-acl --dbname="$RESTORE_TEST_DATABASE_URL" /secure-backups/beautyos-staging.dump`
- قبل از اجرای restore، اتصال مقصد را دستی بازبینی و تأیید کنید؛ برای بازگردانی دیتابیس تولید از این دستورالعمل آزمایشی استفاده نکنید.
- پس از بازیابی، بررسی کامل داده‌ها، تعداد رکوردهای کلیدی، رابطه نوبت/مشتری/فاکتور، و وجود فایل‌ها؛ سپس تست read-only health، ورود و smoke.
- مدت زمان بازیابی، نقطه بازیابی و نتیجه را ثبت کنید. **صرف ایجاد فایل dump به معنی موفق بودن بکاپ نیست.**

## Rollback و Go/No-Go

- پیش از هر انتشار تگ SHA نسخه سالم و سازگاری migrationهای دو نسخه را بررسی کنید.
- Rollback اپلیکیشن فقط در صورت سازگاری Schema؛ هرگز کورکورانه Migration را معکوس نکنید.
- با خرابی ارتباط دیتابیس، سلامت آماده‌به‌کار باید 503 برگرداند و upstream نباید به آن ترافیک بدهد.
- خطاهای OTP و تراکنش مالی باید ثبت و هشداردهی شوند، بدون افشای کدهای OTP یا اطلاعات کارت.
- **درگاه و اشتراک فاز ششم هنوز کامل نشده‌اند**؛ این فاز جایگزین تست عملی آن‌ها نیست.

### شرط تحویل نهایی فاز ۸

- GitHub Actions کامل روی SHA منتخب سبز باشد.
- Restore واقعی روی مقصد ایزوله و backup رسانه تأیید شده باشد.
- HTTPS، domain، proxy، SMTP/SMS و Storage در Staging بازبینی شوند.
- سناریوهای دستی نقش‌ها و جداسازی Tenant موفق باشند.
- مانیتورینگ، آلارم، لاگ، Runbook و بازگشت به نسخه قبلی آزموده شده باشند.
- تصمیم انتشار Production نیازمند تأیید مستقل اپراتور است.
