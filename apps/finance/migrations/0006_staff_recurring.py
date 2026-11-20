import django.db.models.deletion
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [("finance", "0005_accounts_refunds"), ("staff", "0002_staffprofile_calendar_color"), ("expenses", "0002_align_model_state")]
    operations = [
        migrations.CreateModel(name="StaffAgreement", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("salon", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_set", to="salons.salon")),
            ("staff", models.ForeignKey(to="staff.staffprofile", on_delete=django.db.models.deletion.PROTECT, related_name="finance_agreements")),
            ("effective_month", models.DateField()),
            ("mode", models.CharField(max_length=12, choices=[("commission","درصدی"),("salary","حقوق ثابت"),("hybrid","ترکیبی"),("rent","اجاره جایگاه")])),
            ("monthly_toman", models.BigIntegerField(default=0)),
        ], options={"constraints": [models.UniqueConstraint(fields=["salon","staff","effective_month"],name="finance_staff_agreement_month")]}),
        migrations.CreateModel(name="StaffPeriod", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("salon", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_set", to="salons.salon")),
            ("staff", models.ForeignKey(to="staff.staffprofile", on_delete=django.db.models.deletion.PROTECT, related_name="finance_periods")),
            ("agreement", models.ForeignKey(to="finance.staffagreement", on_delete=django.db.models.deletion.PROTECT, related_name="periods")),
            ("month", models.DateField()),
            ("kind", models.CharField(max_length=10, choices=[("salary","حقوق"),("rent","اجاره جایگاه")])),
            ("amount_toman", models.BigIntegerField()),
        ], options={"constraints": [models.UniqueConstraint(fields=["salon","staff","month"],name="finance_staff_period_month")]}),
        migrations.CreateModel(name="StaffPeriodPayment", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("salon", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_set", to="salons.salon")),
            ("period", models.ForeignKey(to="finance.staffperiod", on_delete=django.db.models.deletion.PROTECT, related_name="payments")),
            ("kind", models.CharField(max_length=12, choices=[("advance","مساعده حقوق"),("settlement","تسویه حقوق"),("rent","دریافت اجاره")])),
            ("amount_toman", models.BigIntegerField()),
            ("request_key", models.UUIDField()),
            ("note", models.CharField(max_length=255, blank=True)),
        ], options={"constraints": [models.UniqueConstraint(fields=["salon","request_key"],name="finance_staff_payment_request"), models.CheckConstraint(condition=models.Q(amount_toman__gt=0),name="finance_staff_payment_positive")]}),
        migrations.CreateModel(name="RecurringExpense", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("salon", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_set", to="salons.salon")),
            ("title", models.CharField(max_length=120)),
            ("category", models.CharField(max_length=20)),
            ("amount_toman", models.BigIntegerField()),
            ("next_due", models.DateField()),
            ("day_of_month", models.PositiveSmallIntegerField()),
            ("is_active", models.BooleanField(default=True)),
        ]),
        migrations.CreateModel(name="ExpenseOccurrence", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
            ("salon", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="%(app_label)s_%(class)s_set", to="salons.salon")),
            ("schedule", models.ForeignKey(to="finance.recurringexpense", on_delete=django.db.models.deletion.PROTECT, related_name="occurrences")),
            ("due_day", models.DateField()),
            ("expense", models.OneToOneField(to="expenses.expense", on_delete=django.db.models.deletion.PROTECT, related_name="recurring_occurrence")),
        ], options={"constraints": [models.UniqueConstraint(fields=["salon","schedule","due_day"],name="finance_expense_occurrence_day")]}),
    ]
