from rest_framework import serializers
from .models import Doubt, DoubtReply


class DoubtReplySerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True)

    class Meta:
        model = DoubtReply
        fields = [
            'id', 'doubt', 'author', 'author_username',
            'body', 'is_accepted_answer', 'created_at'
        ]
        read_only_fields = ['id', 'doubt', 'author', 'is_accepted_answer', 'created_at']


class DoubtSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True)
    topic_title = serializers.CharField(source='topic.title', read_only=True, default=None)
    replies_count = serializers.IntegerField(source='replies.count', read_only=True)

    class Meta:
        model = Doubt
        fields = [
            'id', 'classroom', 'topic', 'topic_title', 'author', 'author_username',
            'title', 'body', 'is_resolved', 'replies_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'classroom', 'author', 'is_resolved', 'created_at', 'updated_at']


class DoubtDetailSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True)
    topic_title = serializers.CharField(source='topic.title', read_only=True, default=None)
    replies = DoubtReplySerializer(many=True, read_only=True)

    class Meta:
        model = Doubt
        fields = [
            'id', 'classroom', 'topic', 'topic_title', 'author', 'author_username',
            'title', 'body', 'is_resolved', 'replies',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'classroom', 'author', 'is_resolved', 'created_at', 'updated_at']
