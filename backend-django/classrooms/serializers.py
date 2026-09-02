from rest_framework import serializers
from accounts.serializers import PublicUserSerializer
from .models import Classroom, ClassroomMembership


class ClassroomSerializer(serializers.ModelSerializer):
    teacher = PublicUserSerializer(read_only=True)
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Classroom
        fields = ('id', 'name', 'description', 'teacher', 'member_count', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')

    def get_member_count(self, obj):
        return obj.memberships.filter(status=ClassroomMembership.MembershipStatus.ACTIVE).count()


class ClassroomCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Classroom
        fields = ('id', 'name', 'description')

    def validate(self, attrs):
        user = self.context['request'].user
        if user.role != 'TEACHER':
            raise serializers.ValidationError("Only users with the TEACHER role can create classrooms.")
        return attrs

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
        return classroom
