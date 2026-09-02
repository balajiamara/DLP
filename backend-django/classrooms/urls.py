from django.urls import path
from .views import ClassroomListCreateView, ClassroomDetailView, CreateJoinTokenView

urlpatterns = [
    path('', ClassroomListCreateView.as_view(), name='classroom_list_create'),
    path('<int:pk>/', ClassroomDetailView.as_view(), name='classroom_detail'),
    path('<int:pk>/join-links/', CreateJoinTokenView.as_view(), name='create_join_token'),
]
