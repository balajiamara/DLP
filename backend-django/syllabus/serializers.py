from rest_framework import serializers
from .models import Course, Module, Topic, Resource, TopicProgress, Material


class ResourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resource
        fields = ['id', 'topic', 'title', 'resource_type', 'url_or_note', 'order', 'created_at']
        read_only_fields = ['id', 'topic', 'created_at']


class TopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Topic
        fields = ['id', 'module', 'title', 'description', 'order', 'created_at']
        read_only_fields = ['id', 'module', 'created_at']


class TopicDetailSerializer(serializers.ModelSerializer):
    resources = ResourceSerializer(many=True, read_only=True)

    class Meta:
        model = Topic
        fields = ['id', 'module', 'title', 'description', 'order', 'created_at', 'resources']
        read_only_fields = ['id', 'module', 'created_at', 'resources']


class ModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Module
        fields = ['id', 'course', 'title', 'description', 'order', 'created_at']
        read_only_fields = ['id', 'course', 'created_at']


class ModuleDetailSerializer(serializers.ModelSerializer):
    topics = TopicDetailSerializer(many=True, read_only=True)

    class Meta:
        model = Module
        fields = ['id', 'course', 'title', 'description', 'order', 'created_at', 'topics']
        read_only_fields = ['id', 'course', 'created_at', 'topics']


class CourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = ['id', 'classroom', 'title', 'description', 'order', 'created_at']
        read_only_fields = ['id', 'classroom', 'created_at']


class CourseDetailSerializer(serializers.ModelSerializer):
    modules = ModuleDetailSerializer(many=True, read_only=True)

    class Meta:
        model = Course
        fields = ['id', 'classroom', 'title', 'description', 'order', 'created_at', 'modules']
        read_only_fields = ['id', 'classroom', 'created_at', 'modules']


class TopicProgressSerializer(serializers.ModelSerializer):
    class Meta:
        model = TopicProgress
        fields = ['id', 'student', 'topic', 'learning_state', 'updated_at']
        read_only_fields = ['id', 'student', 'topic', 'updated_at']


class TopicProgressUpdateSerializer(serializers.Serializer):
    learning_state = serializers.ChoiceField(choices=TopicProgress.LearningState.choices)


class MaterialSerializer(serializers.ModelSerializer):
    uploaded_by_username = serializers.CharField(source='uploaded_by.username', read_only=True)

    class Meta:
        model = Material
        fields = [
            'id', 'topic', 'uploaded_by', 'uploaded_by_username',
            'title', 'file_name', 'file_type', 'file_size_bytes',
            'status', 'created_at'
        ]
        read_only_fields = [
            'id', 'topic', 'uploaded_by', 'file_name',
            'file_type', 'file_size_bytes', 'status', 'created_at'
        ]


