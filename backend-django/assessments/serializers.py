from rest_framework import serializers
from .models import Assignment, Submission, Quiz, Question, QuizAttempt


class AssignmentSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    topic_title = serializers.CharField(source='topic.title', read_only=True, default=None)

    class Meta:
        model = Assignment
        fields = [
            'id', 'classroom', 'topic', 'topic_title',
            'title', 'description', 'due_date',
            'created_by', 'created_by_username', 'created_at'
        ]
        read_only_fields = ['id', 'classroom', 'created_by', 'created_at']


class SubmissionSerializer(serializers.ModelSerializer):
    student_username = serializers.CharField(source='student.username', read_only=True)

    class Meta:
        model = Submission
        fields = [
            'id', 'assignment', 'student', 'student_username',
            'content', 'submitted_at', 'feedback', 'grade'
        ]
        read_only_fields = ['id', 'assignment', 'student', 'submitted_at', 'feedback', 'grade']


class SubmissionFeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Submission
        fields = ['feedback', 'grade']


class QuestionStudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = ['id', 'quiz', 'text', 'option_a', 'option_b', 'option_c', 'option_d', 'order']
        read_only_fields = ['id', 'quiz']


class QuestionTeacherSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = ['id', 'quiz', 'text', 'option_a', 'option_b', 'option_c', 'option_d', 'correct_option', 'order']
        read_only_fields = ['id', 'quiz']


class QuizSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    topic_title = serializers.CharField(source='topic.title', read_only=True, default=None)
    questions_count = serializers.IntegerField(source='questions.count', read_only=True)

    class Meta:
        model = Quiz
        fields = [
            'id', 'classroom', 'topic', 'topic_title',
            'title', 'created_by', 'created_by_username',
            'questions_count', 'created_at'
        ]
        read_only_fields = ['id', 'classroom', 'created_by', 'created_at']


class QuizCreateSerializer(serializers.ModelSerializer):
    questions = QuestionTeacherSerializer(many=True, required=False)

    class Meta:
        model = Quiz
        fields = ['id', 'classroom', 'topic', 'title', 'questions', 'created_at']
        read_only_fields = ['id', 'classroom', 'created_at']

    def create(self, validated_data):
        questions_data = validated_data.pop('questions', [])
        quiz = Quiz.objects.create(**validated_data)
        for idx, q_data in enumerate(questions_data):
            if 'order' not in q_data:
                q_data['order'] = idx + 1
            Question.objects.create(quiz=quiz, **q_data)
        return quiz


class QuizDetailSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    topic_title = serializers.CharField(source='topic.title', read_only=True, default=None)
    questions = serializers.SerializerMethodNestedField if False else serializers.SerializerMethodField()

    class Meta:
        model = Quiz
        fields = [
            'id', 'classroom', 'topic', 'topic_title',
            'title', 'created_by', 'created_by_username',
            'questions', 'created_at'
        ]
        read_only_fields = ['id', 'classroom', 'created_by', 'created_at']

    def get_questions(self, obj):
        request = self.context.get('request')
        is_teacher = request and request.user == obj.classroom.teacher
        has_attempted = False

        if request and not is_teacher:
            has_attempted = QuizAttempt.objects.filter(quiz=obj, student=request.user).exists()

        if is_teacher or has_attempted:
            serializer = QuestionTeacherSerializer(obj.questions.all(), many=True)
        else:
            serializer = QuestionStudentSerializer(obj.questions.all(), many=True)

        return serializer.data


class QuizAttemptSerializer(serializers.ModelSerializer):
    student_username = serializers.CharField(source='student.username', read_only=True)

    class Meta:
        model = QuizAttempt
        fields = ['id', 'quiz', 'student', 'student_username', 'answers', 'score', 'attempted_at']
        read_only_fields = ['id', 'quiz', 'student', 'score', 'attempted_at']
