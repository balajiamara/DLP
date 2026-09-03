from django.urls import path
from .views import (
    DoubtListCreateView,
    DoubtDetailView,
    DoubtReplyListCreateView,
    DoubtReplyAcceptView,
    DoubtReplyDetailView,
)

urlpatterns = [
    path('', DoubtListCreateView.as_view(), name='doubt_list_create'),
    path('<int:pk>/', DoubtDetailView.as_view(), name='doubt_detail'),
    path('<int:doubt_id>/replies/', DoubtReplyListCreateView.as_view(), name='doubt_reply_list_create'),
    path('<int:doubt_id>/replies/<int:reply_id>/accept/', DoubtReplyAcceptView.as_view(), name='doubt_reply_accept'),
    path('<int:doubt_id>/replies/<int:reply_id>/', DoubtReplyDetailView.as_view(), name='doubt_reply_detail'),
]
