from django.urls import path
from .views import (
    GroupListCreateView,
    GroupDetailView,
    AddGroupMemberView,
    LeaveGroupView,
)

urlpatterns = [
    path('', GroupListCreateView.as_view(), name='group_list_create'),
    path('<int:pk>/', GroupDetailView.as_view(), name='group_detail'),
    path('<int:pk>/members/', AddGroupMemberView.as_view(), name='add_group_member'),
    path('<int:pk>/leave/', LeaveGroupView.as_view(), name='leave_group'),
]
