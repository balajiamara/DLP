from django.contrib import admin
from .models import Doubt, DoubtReply


class DoubtReplyInline(admin.TabularInline):
    model = DoubtReply
    extra = 1


@admin.register(Doubt)
class DoubtAdmin(admin.ModelAdmin):
    list_display = ('title', 'classroom', 'topic', 'author', 'is_resolved', 'created_at')
    list_filter = ('is_resolved', 'classroom')
    search_fields = ('title', 'body', 'author__username')
    inlines = [DoubtReplyInline]


@admin.register(DoubtReply)
class DoubtReplyAdmin(admin.ModelAdmin):
    list_display = ('doubt', 'author', 'is_accepted_answer', 'created_at')
    list_filter = ('is_accepted_answer', 'doubt__classroom')
    search_fields = ('body', 'author__username', 'doubt__title')
