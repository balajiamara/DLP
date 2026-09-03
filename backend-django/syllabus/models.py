from django.db import models
from django.conf import settings
from classrooms.models import Classroom


class Course(models.Model):
    classroom = models.ForeignKey(
        Classroom,
        on_delete=models.CASCADE,
        related_name='courses'
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'created_at']

    def __str__(self):
        return f"{self.title} ({self.classroom.name})"


class Module(models.Model):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='modules'
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'created_at']

    def __str__(self):
        return f"{self.title} - Course: {self.course.title}"


class Topic(models.Model):
    module = models.ForeignKey(
        Module,
        on_delete=models.CASCADE,
        related_name='topics'
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'created_at']

    def __str__(self):
        return f"{self.title} - Module: {self.module.title}"


class Resource(models.Model):
    class ResourceType(models.TextChoices):
        DOCUMENT = 'DOCUMENT', 'Document'
        LINK = 'LINK', 'Link'
        NOTE = 'NOTE', 'Note'

    topic = models.ForeignKey(
        Topic,
        on_delete=models.CASCADE,
        related_name='resources'
    )
    title = models.CharField(max_length=255)
    resource_type = models.CharField(
        max_length=20,
        choices=ResourceType.choices,
        default=ResourceType.LINK
    )
    url_or_note = models.TextField(blank=True, default='')
    order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'created_at']

    def __str__(self):
        return f"{self.title} ({self.resource_type}) - Topic: {self.topic.title}"


class TopicProgress(models.Model):
    class LearningState(models.TextChoices):
        NOT_STARTED = 'NOT_STARTED', 'Not Started'
        LEARNING = 'LEARNING', 'Learning'
        PRACTICING = 'PRACTICING', 'Practicing'
        COMPLETED = 'COMPLETED', 'Completed'
        REVIEW_REQUIRED = 'REVIEW_REQUIRED', 'Review Required'
        MASTERED = 'MASTERED', 'Mastered'

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='topic_progresses'
    )
    topic = models.ForeignKey(
        Topic,
        on_delete=models.CASCADE,
        related_name='progresses'
    )
    learning_state = models.CharField(
        max_length=20,
        choices=LearningState.choices,
        default=LearningState.NOT_STARTED
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'topic'],
                name='unique_student_topic_progress'
            )
        ]

    def __str__(self):
        return f"{self.student.username} - {self.topic.title}: {self.learning_state}"


class Material(models.Model):
    class MaterialStatus(models.TextChoices):
        UPLOADED = 'UPLOADED', 'Uploaded'
        PROCESSING = 'PROCESSING', 'Processing'
        READY = 'READY', 'Ready'
        FAILED = 'FAILED', 'Failed'

    topic = models.ForeignKey(
        Topic,
        on_delete=models.CASCADE,
        related_name='materials'
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='uploaded_materials'
    )
    title = models.CharField(max_length=255)
    file_name = models.CharField(max_length=255)
    storage_path = models.CharField(max_length=512)
    file_type = models.CharField(max_length=50)
    file_size_bytes = models.BigIntegerField()
    status = models.CharField(
        max_length=20,
        choices=MaterialStatus.choices,
        default=MaterialStatus.UPLOADED
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.file_type}) - Topic: {self.topic.title}"


