from rest_framework import serializers
from accounts.serializers import PublicUserSerializer
from .models import Group, GroupMembership


class GroupSerializer(serializers.ModelSerializer):
    created_by = PublicUserSerializer(read_only=True)
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = ('id', 'name', 'description', 'created_by', 'member_count', 'created_at')
        read_only_fields = ('id', 'created_at')

    def get_member_count(self, obj):
        return obj.memberships.filter(status=GroupMembership.MembershipStatus.ACTIVE).count()


class GroupCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ('id', 'name', 'description')

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
        return group
