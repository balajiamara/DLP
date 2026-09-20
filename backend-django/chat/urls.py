from django.urls import path
from .views import CourseChatStreamProxyView, GeneralChatStreamProxyView, ChatFeedbackProxyView

urlpatterns = [
    path('course/stream', CourseChatStreamProxyView.as_view(), name='course_chat_stream'),
    path('general/stream', GeneralChatStreamProxyView.as_view(), name='general_chat_stream'),
    path('feedback', ChatFeedbackProxyView.as_view(), name='chat_feedback'),
    path('feedback/', ChatFeedbackProxyView.as_view()),
]
