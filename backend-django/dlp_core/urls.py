from django.contrib import admin
from django.urls import path, include
from accounts.views import UserSearchView
from classrooms.views import JoinClassroomView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('accounts.urls')),
    path('api/users/search/', UserSearchView.as_view(), name='user_search'),
    path('api/classrooms/', include('classrooms.urls')),
    path('api/join/<str:token>/', JoinClassroomView.as_view(), name='join_classroom'),
    path('api/groups/', include('groups.urls')),
]
