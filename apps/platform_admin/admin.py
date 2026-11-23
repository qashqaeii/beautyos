from django.contrib import admin

from apps.platform_admin.models import SupportMessage, SupportTicket


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
