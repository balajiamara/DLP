from rest_framework import serializers
from accounts.serializers import PublicUserSerializer
from .models import Group, GroupMembership


class GroupSerializer(serializers.ModelSerializer):
    created_by = PublicUserSerializer(read_only=True)
    member_count = serializers.SerializerMethodField()
    conversation_id = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = ('id', 'name', 'description', 'created_by', 'member_count', 'conversation_id', 'created_at')
        read_only_fields = ('id', 'created_at', 'conversation_id')

    def get_member_count(self, obj):
        return obj.memberships.filter(status=GroupMembership.MembershipStatus.ACTIVE).count()

    def get_conversation_id(self, obj):
        return obj.conversation.filter(type='GROUP').values_list('id', flat=True).first()


from django.db import transaction


class GroupCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ('id', 'name', 'description')

    @transaction.atomic
    def create(self, validated_data):
        user = self.context['request'].user
        group = Group.objects.create(
            name=validated_data['name'],
            description=validated_data.get('description', ''),
            created_by=user
        )
        # Automatically add creator as an active member
        GroupMembership.objects.create(
            user=user,
            group=group,
            status=GroupMembership.MembershipStatus.ACTIVE
        )
        # Automatically provision GROUP-type Conversation
        from conversations.models import Conversation
        Conversation.objects.create(
            group=group,
            type=Conversation.Type.GROUP
        )
        return group

