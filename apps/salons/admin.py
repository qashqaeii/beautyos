from django.contrib import admin

from apps.salons.models import Salon, SalonMembership, SalonSettings


class SalonSettingsInline(admin.StackedInline):
    model = SalonSettings
    extra = 0


@admin.register(Salon)
class SalonAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "city", "is_active", "public_theme", "created_at")
    search_fields = ("name", "slug", "city")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [SalonSettingsInline]


@admin.register(SalonMembership)
class SalonMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "salon", "role", "is_active", "created_at")
    list_filter = ("role", "is_active")
    search_fields = ("user__phone", "salon__name")


@admin.register(SalonSettings)
class SalonSettingsAdmin(admin.ModelAdmin):
    list_display = ("salon", "timezone", "currency_code")
