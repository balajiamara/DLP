from rest_framework import serializers
from django.contrib.auth import get_user_model
from accounts.serializers import PublicUserSerializer
from .models import Conversation, Message

User = get_user_model()


class MessageSerializer(serializers.ModelSerializer):
    sender = PublicUserSerializer(read_only=True)
    conversation_id = serializers.IntegerField(source='conversation.id', read_only=True)

    class Meta:
        model = Message
        fields = ('id', 'conversation_id', 'sender', 'body', 'created_at')
        read_only_fields = ('id', 'conversation_id', 'sender', 'created_at')


class MessageCreateSerializer(serializers.Serializer):
    body = serializers.CharField(required=True, max_length=5000, trim_whitespace=True)

    def validate_body(self, value):
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError("Message body cannot be empty.")
        return cleaned


class ConversationListSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    entity_id = serializers.SerializerMethodField()
    other_user = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = (
            'id',
            'type',
            'title',
            'entity_id',
            'other_user',
            'last_message',
            'created_at',
            'updated_at',
        )

    def _get_other_user(self, obj):
        request = self.context.get('request')
        if not request or obj.type != Conversation.Type.DIRECT:
            return None
        if obj.user_a_id == request.user.id:
            return obj.user_b
        return obj.user_a

    def get_title(self, obj):
        if obj.type == Conversation.Type.CLASSROOM and obj.classroom:
            return obj.classroom.name
        if obj.type == Conversation.Type.GROUP and obj.group:
            return obj.group.name
        if obj.type == Conversation.Type.DIRECT:
            other = self._get_other_user(obj)
            return other.username if other else 'Direct Message'
        return f"Conversation {obj.id}"

    def get_entity_id(self, obj):
        if obj.type == Conversation.Type.CLASSROOM:
            return obj.classroom_id
        if obj.type == Conversation.Type.GROUP:
            return obj.group_id
        if obj.type == Conversation.Type.DIRECT:
            other = self._get_other_user(obj)
            return other.id if other else None
        return None

    def get_other_user(self, obj):
        if obj.type == Conversation.Type.DIRECT:
            other = self._get_other_user(obj)
            if other:
                return PublicUserSerializer(other).data
        return None

    def get_last_message(self, obj):
        # Optimized via prefetch_related or fallback to slice
        msg = obj.messages.order_by('-created_at').first()
        if not msg:
            return None
        return {
            'id': msg.id,
            'body': msg.body,
            'sender': {
                'id': msg.sender_id,
                'username': msg.sender.username,
            },
            'sender_username': msg.sender.username,
            'created_at': msg.created_at,
        }


class DirectConversationCreateSerializer(serializers.Serializer):
    target_user_id = serializers.IntegerField(required=True)

    def validate_target_user_id(self, value):
        request = self.context.get('request')
        if request and request.user.id == value:
            raise serializers.ValidationError("Cannot start a direct conversation with yourself.")
        try:
            target_user = User.objects.get(pk=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("Target user does not exist.")
        return value
