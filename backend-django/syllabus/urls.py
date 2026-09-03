from django.urls import path
from .views import (
    CourseListCreateView,
    CourseDetailView,
    ModuleCreateView,
    ModuleDetailView,
    TopicCreateView,
    TopicDetailView,
    ResourceCreateView,
    ResourceDetailView,
    StudentClassroomProgressView,
    StudentProgressSummaryView,
)

urlpatterns = [
    # Courses
    path('courses/', CourseListCreateView.as_view(), name='course_list_create'),
    path('courses/<int:pk>/', CourseDetailView.as_view(), name='course_detail'),

    # Modules
    path('courses/<int:course_id>/modules/', ModuleCreateView.as_view(), name='module_create'),
    path('modules/<int:pk>/', ModuleDetailView.as_view(), name='module_detail'),

    # Topics
    path('modules/<int:module_id>/topics/', TopicCreateView.as_view(), name='topic_create'),
    path('topics/<int:pk>/', TopicDetailView.as_view(), name='topic_detail'),

    # Resources
    path('topics/<int:topic_id>/resources/', ResourceCreateView.as_view(), name='resource_create'),
    path('resources/<int:pk>/', ResourceDetailView.as_view(), name='resource_detail'),

    # Progress Tracking
    path('my-progress/', StudentClassroomProgressView.as_view(), name='student_classroom_progress'),
    path('progress-summary/', StudentProgressSummaryView.as_view(), name='student_progress_summary'),
]

