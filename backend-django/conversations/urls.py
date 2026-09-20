from django.urls import path
from .views import (
    ConversationListView,
    ConversationMessagesView,
    DirectConversationFindOrCreateView,
)

urlpatterns = [
    path('', ConversationListView.as_view(), name='conversation_list'),
    path('<int:pk>/messages/', ConversationMessagesView.as_view(), name='conversation_messages'),
    path('direct/', DirectConversationFindOrCreateView.as_view(), name='conversation_direct'),
]
