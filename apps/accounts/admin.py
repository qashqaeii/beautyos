from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from apps.accounts.models import OTPChallenge, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ("phone",)
    list_display = ("phone", "full_name", "is_staff", "is_active", "created_at")
    search_fields = ("phone", "full_name")
    fieldsets = (
        (None, {"fields": ("phone", "password")}),
        ("اطلاعات", {"fields": ("full_name",)}),
        ("دسترسی", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("زمان", {"fields": ("last_login", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("phone", "password1", "password2", "full_name")}),
    )
    readonly_fields = ("created_at", "updated_at", "last_login")


@admin.register(OTPChallenge)
class OTPChallengeAdmin(admin.ModelAdmin):
    list_display = ("phone", "purpose", "expires_at", "attempts", "consumed_at", "created_at")
    list_filter = ("purpose",)
    search_fields = ("phone",)
