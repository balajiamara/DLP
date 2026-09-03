from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from .models import Notification
from .serializers import NotificationSerializer


class NotificationPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class NotificationListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        queryset = Notification.objects.filter(recipient=request.user)

        unread_param = request.query_params.get('unread')
        if unread_param is not None and unread_param.lower() in ('true', '1'):
            queryset = queryset.filter(is_read=False)

        paginator = NotificationPagination()
        page = paginator.paginate_queryset(queryset, request)
        if page is not None:
            serializer = NotificationSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = NotificationSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class NotificationUnreadCountView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        count = Notification.objects.filter(recipient=request.user, is_read=False).count()
        return Response({'unread_count': count}, status=status.HTTP_200_OK)


class NotificationMarkReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, pk):
        notification = get_object_or_404(Notification, pk=pk)

        if notification.recipient != request.user:
            raise PermissionDenied("Only the recipient can mark this notification as read.")

        notification.is_read = True
        notification.save()
        return Response(NotificationSerializer(notification).data, status=status.HTTP_200_OK)


class NotificationMarkAllReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        updated_count = Notification.objects.filter(
            recipient=request.user,
            is_read=False
        ).update(is_read=True)

        return Response({
            'detail': 'All notifications marked as read.',
            'updated_count': updated_count
        }, status=status.HTTP_200_OK)
