from django.contrib import admin

from apps.website.models import BlogPost, ContactInquiry


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "category", "published_at", "created_at")
    list_filter = ("status", "category")
    search_fields = ("title", "summary", "body")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("created_at", "updated_at")

@admin.register(ContactInquiry)
class ContactInquiryAdmin(admin.ModelAdmin):
    list_display = ("name", "topic", "status", "phone", "created_at")
    list_filter = ("status", "topic", "created_at")
    search_fields = ("name", "phone", "email", "message")
    readonly_fields = (
        "name", "phone", "email", "topic", "message",
        "ip_digest", "consented_at", "created_at", "updated_at",
    )
    fields = (
        "name", "phone", "email", "topic", "message",
        "status", "internal_note", "handled_by",
        "ip_digest", "consented_at", "created_at", "updated_at",
    )
