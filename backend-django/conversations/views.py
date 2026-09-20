from rest_framework import permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import NotFound
from django.shortcuts import get_object_or_404
from django.db import models
from django.utils.dateparse import parse_datetime

from .models import Conversation, Message
from .serializers import (
    ConversationListSerializer,
    MessageSerializer,
    MessageCreateSerializer,
    DirectConversationCreateSerializer,
)
from .services import check_conversation_access
from .broadcast import dispatch_conversation_broadcast
from classrooms.models import ClassroomMembership
from groups.models import GroupMembership



class ConversationListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        conversations = Conversation.objects.filter(
            models.Q(
                type=Conversation.Type.CLASSROOM,
                classroom__memberships__user=user,
                classroom__memberships__status=ClassroomMembership.MembershipStatus.ACTIVE
            ) |
            models.Q(
                type=Conversation.Type.GROUP,
                group__memberships__user=user,
                group__memberships__status=GroupMembership.MembershipStatus.ACTIVE
            ) |
            models.Q(type=Conversation.Type.DIRECT, user_a=user) |
            models.Q(type=Conversation.Type.DIRECT, user_b=user)
        ).distinct().select_related(
            'classroom', 'group', 'user_a', 'user_b'
        ).order_by('-updated_at')

        serializer = ConversationListSerializer(
            conversations,
            many=True,
            context={'request': request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)


class ConversationMessagesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def _get_conversation(self, request, pk):
        conversation = get_object_or_404(
            Conversation.objects.select_related('classroom', 'group', 'user_a', 'user_b'),
            pk=pk
        )
        if not check_conversation_access(request.user, conversation):
            raise NotFound("Conversation not found.")
        return conversation

    def get(self, request, pk):
        conversation = self._get_conversation(request, pk)

        # Parse limit
        try:
            limit = int(request.query_params.get('limit', 50))
            limit = max(1, min(limit, 100))
        except (ValueError, TypeError):
            limit = 50

        # Parse before cursor (ISO datetime)
        before_param = request.query_params.get('before')
        messages_qs = conversation.messages.select_related('sender')

        if before_param:
            clean_param = before_param.strip()
            if ' ' in clean_param and '+' not in clean_param:
                clean_param = '+'.join(clean_param.rsplit(' ', 1))
            parsed_dt = parse_datetime(clean_param)
            if parsed_dt:
                messages_qs = messages_qs.filter(created_at__lt=parsed_dt)


        # Fetch limit + 1 to check for has_more
        slice_qs = list(messages_qs.order_by('-created_at')[:limit + 1])
        has_more = len(slice_qs) > limit
        items = slice_qs[:limit]

        # Chronological order (oldest to newest) for client-side chat rendering
        items.reverse()
        oldest_timestamp = items[0].created_at.isoformat() if items else None

        serializer = MessageSerializer(items, many=True)
        return Response({
            'messages': serializer.data,
            'has_more': has_more,
            'oldest_timestamp': oldest_timestamp,
        }, status=status.HTTP_200_OK)

    def post(self, request, pk):
        conversation = self._get_conversation(request, pk)

        serializer = MessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        message = Message.objects.create(
            conversation=conversation,
            sender=request.user,
            body=serializer.validated_data['body']
        )
        conversation.save(update_fields=['updated_at'])

        output_data = MessageSerializer(message).data
        # Fire-and-forget real-time broadcast to FastAPI conversation room
        dispatch_conversation_broadcast(
            event_type="message_created",
            conversation_id=conversation.id,
            payload=output_data,
        )

        return Response(
            output_data,
            status=status.HTTP_201_CREATED
        )



class DirectConversationFindOrCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = DirectConversationCreateSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        target_user_id = serializer.validated_data['target_user_id']

        user_a_id = min(request.user.id, target_user_id)
        user_b_id = max(request.user.id, target_user_id)

        conversation, created = Conversation.objects.get_or_create(
            type=Conversation.Type.DIRECT,
            user_a_id=user_a_id,
            user_b_id=user_b_id
        )

        resp_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        output = ConversationListSerializer(conversation, context={'request': request})
        return Response(output.data, status=resp_status)
