from django.contrib import admin
from .models import Course, Module, Topic, Resource, TopicProgress, Material


class ResourceInline(admin.TabularInline):
    model = Resource
    extra = 1


class TopicInline(admin.TabularInline):
    model = Topic
    extra = 1


class ModuleInline(admin.TabularInline):
    model = Module
    extra = 1


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'classroom', 'order', 'created_at')
    list_filter = ('classroom',)
    search_fields = ('title', 'description')
    inlines = [ModuleInline]


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'order', 'created_at')
    list_filter = ('course__classroom', 'course')
    search_fields = ('title', 'description')
    inlines = [TopicInline]


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('title', 'module', 'order', 'created_at')
    list_filter = ('module__course__classroom', 'module__course', 'module')
    search_fields = ('title', 'description')
    inlines = [ResourceInline]


@admin.register(Resource)
class ResourceAdmin(admin.ModelAdmin):
    list_display = ('title', 'resource_type', 'topic', 'order', 'created_at')
    list_filter = ('resource_type', 'topic__module__course__classroom')
    search_fields = ('title', 'url_or_note')


@admin.register(TopicProgress)
class TopicProgressAdmin(admin.ModelAdmin):
    list_display = ('student', 'topic', 'learning_state', 'updated_at')
    list_filter = ('learning_state', 'topic__module__course__classroom')
    search_fields = ('student__username', 'student__email', 'topic__title')


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ('title', 'file_name', 'file_type', 'file_size_bytes', 'status', 'topic', 'uploaded_by', 'created_at')
    list_filter = ('file_type', 'status', 'topic__module__course__classroom')
    search_fields = ('title', 'file_name', 'storage_path')


