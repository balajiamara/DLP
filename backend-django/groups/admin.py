from django.contrib import admin
from .models import Group, GroupMembership


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'created_by', 'created_at')
    search_fields = ('name', 'description', 'created_by__email', 'created_by__username')
    list_filter = ('created_at',)


@admin.register(GroupMembership)
class GroupMembershipAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'group', 'status', 'joined_at')
    list_filter = ('status', 'joined_at')
    search_fields = ('user__email', 'user__username', 'group__name')
