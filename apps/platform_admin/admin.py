from django.contrib import admin

from apps.platform_admin.models import SupportMessage, SupportTicket, SubscriptionPlan, SalonSubscription


class SupportMessageInline(admin.TabularInline):
    model = SupportMessage
    extra = 0
    readonly_fields = ("author", "body", "is_internal", "created_at")


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "salon", "category", "status", "priority", "last_activity_at")
    list_filter = ("status", "priority", "category")
    search_fields = ("title", "salon__name")
    readonly_fields = ("opened_by", "salon", "created_at", "updated_at")
    inlines = [SupportMessageInline]


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "price_toman", "period_days", "trial_days", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")
    readonly_fields = ("created_at", "updated_at")

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SalonSubscription)
class SalonSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("salon", "plan", "status", "starts_at", "ends_at")
    list_filter = ("status", "plan")
    search_fields = ("salon__name", "salon__slug")
    autocomplete_fields = ("salon", "plan")
    readonly_fields = ("created_at", "updated_at")

    def has_delete_permission(self, request, obj=None):
        return False
