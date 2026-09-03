from django.urls import path
from .views import (
    ClassroomListCreateView,
    ClassroomDetailView,
    CreateJoinTokenView,
    ClassroomDashboardView,
    ClassroomStudentDetailView,
)

urlpatterns = [
    path('', ClassroomListCreateView.as_view(), name='classroom_list_create'),
    path('<int:pk>/', ClassroomDetailView.as_view(), name='classroom_detail'),
    path('<int:pk>/join-links/', CreateJoinTokenView.as_view(), name='create_join_token'),
    path('<int:classroom_id>/dashboard/', ClassroomDashboardView.as_view(), name='classroom_dashboard'),
    path('<int:classroom_id>/students/<int:student_id>/detail/', ClassroomStudentDetailView.as_view(), name='classroom_student_detail'),
]
