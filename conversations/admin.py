from django.contrib import admin
from .models import Conversation, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    fields = ("role", "content", "intent", "language")
    readonly_fields = ("role", "content", "intent", "language")


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "channel", "status")
    list_filter = ("channel", "status")
    raw_id_fields = ("customer",)
    inlines = [MessageInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "role", "content_preview", "intent")
    list_filter = ("role", "intent")
    raw_id_fields = ("conversation",)

    def content_preview(self, obj):
        return (obj.content[:80] + "...") if len(obj.content) > 80 else obj.content

    content_preview.short_description = "Content"
