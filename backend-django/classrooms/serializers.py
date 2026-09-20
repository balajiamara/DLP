from rest_framework import serializers
from accounts.serializers import PublicUserSerializer
from .models import Classroom, ClassroomMembership


class ClassroomSerializer(serializers.ModelSerializer):
    teacher = PublicUserSerializer(read_only=True)
    member_count = serializers.SerializerMethodField()
    conversation_id = serializers.SerializerMethodField()

    class Meta:
        model = Classroom
        fields = ('id', 'name', 'description', 'teacher', 'member_count', 'conversation_id', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at', 'conversation_id')

    def get_member_count(self, obj):
        return obj.memberships.filter(status=ClassroomMembership.MembershipStatus.ACTIVE).count()

    def get_conversation_id(self, obj):
        return obj.conversation.filter(type='CLASSROOM').values_list('id', flat=True).first()


from django.db import transaction


class ClassroomCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Classroom
        fields = ('id', 'name', 'description')

    def validate(self, attrs):
        user = self.context['request'].user
        if user.role != 'TEACHER':
            raise serializers.ValidationError("Only users with the TEACHER role can create classrooms.")
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        user = self.context['request'].user
        classroom = Classroom.objects.create(
            name=validated_data['name'],
            description=validated_data.get('description', ''),
            teacher=user
        )
        # Automatically add creating teacher as an active member with role TEACHER
        ClassroomMembership.objects.create(
            user=user,
            classroom=classroom,
            role_in_classroom=ClassroomMembership.RoleInClassroom.TEACHER,
            status=ClassroomMembership.MembershipStatus.ACTIVE
        )
        # Automatically provision CLASSROOM-type Conversation
        from conversations.models import Conversation
        Conversation.objects.create(
            classroom=classroom,
            type=Conversation.Type.CLASSROOM
        )
        return classroom

