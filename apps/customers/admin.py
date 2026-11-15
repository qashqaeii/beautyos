from django.contrib import admin

from apps.customers.models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("full_name", "phone", "salon", "last_visit_at", "is_vip")
    search_fields = ("full_name", "phone")
    list_filter = ("is_vip",)
