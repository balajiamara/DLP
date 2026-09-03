from django.db import models
from django.conf import settings
from classrooms.models import Classroom
from syllabus.models import Topic


class Doubt(models.Model):
    classroom = models.ForeignKey(
        Classroom,
        on_delete=models.CASCADE,
        related_name='doubts'
    )
    topic = models.ForeignKey(
        Topic,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='doubts'
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='doubts'
    )
    title = models.CharField(max_length=255)
    body = models.TextField()
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} by {self.author.username} ({self.classroom.name})"


class DoubtReply(models.Model):
    doubt = models.ForeignKey(
        Doubt,
        on_delete=models.CASCADE,
        related_name='replies'
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='doubt_replies'
    )
    body = models.TextField()
    is_accepted_answer = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Reply by {self.author.username} on '{self.doubt.title}'"
