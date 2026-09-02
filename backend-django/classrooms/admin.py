from django.contrib import admin
from .models import Classroom, ClassroomMembership, JoinToken


@admin.register(Classroom)
class ClassroomAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'teacher', 'created_at', 'updated_at')
    search_fields = ('name', 'description', 'teacher__email', 'teacher__username')
    list_filter = ('created_at',)


@admin.register(ClassroomMembership)
class ClassroomMembershipAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'classroom', 'role_in_classroom', 'status', 'joined_at')
    list_filter = ('role_in_classroom', 'status', 'joined_at')
    search_fields = ('user__email', 'user__username', 'classroom__name')


@admin.register(JoinToken)
class JoinTokenAdmin(admin.ModelAdmin):
    list_display = ('id', 'token', 'classroom', 'created_by', 'created_at')
    search_fields = ('token', 'classroom__name', 'created_by__email', 'created_by__username')
    list_filter = ('created_at',)
