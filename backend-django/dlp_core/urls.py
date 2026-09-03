from django.contrib import admin
from django.urls import path, include
from accounts.views import UserSearchView
from classrooms.views import JoinClassroomView
from syllabus.views import (
    TopicProgressUpdateView,
    TopicMaterialListCreateView,
    MaterialDownloadURLView,
    MaterialDetailView,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('accounts.urls')),
    path('api/users/search/', UserSearchView.as_view(), name='user_search'),
    path('api/classrooms/', include('classrooms.urls')),
    path('api/classrooms/<int:classroom_id>/', include('syllabus.urls')),
    path('api/classrooms/<int:classroom_id>/', include('assessments.urls')),
    path('api/classrooms/<int:classroom_id>/doubts/', include('doubts.urls')),
    path('api/topics/<int:topic_id>/my-progress/', TopicProgressUpdateView.as_view(), name='topic_progress_update'),
    path('api/topics/<int:topic_id>/materials/', TopicMaterialListCreateView.as_view(), name='topic_material_list_create'),
    path('api/materials/<int:pk>/download-url/', MaterialDownloadURLView.as_view(), name='material_download_url'),
    path('api/materials/<int:pk>/', MaterialDetailView.as_view(), name='material_detail'),
    path('api/join/<str:token>/', JoinClassroomView.as_view(), name='join_classroom'),
    path('api/groups/', include('groups.urls')),
    path('api/notifications/', include('notifications.urls')),
]

