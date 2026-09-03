from django.db import models
from django.conf import settings


class Notification(models.Model):
    class NotificationType(models.TextChoices):
        NEW_MATERIAL = 'NEW_MATERIAL', 'New Material'
        DOUBT_REPLY = 'DOUBT_REPLY', 'Doubt Reply'
        DOUBT_ACCEPTED = 'DOUBT_ACCEPTED', 'Doubt Answer Accepted'
        ASSIGNMENT_DUE_SOON = 'ASSIGNMENT_DUE_SOON', 'Assignment Due Soon'
        ASSIGNMENT_GRADED = 'ASSIGNMENT_GRADED', 'Assignment Graded'
        NEW_QUIZ = 'NEW_QUIZ', 'New Quiz'

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    notification_type = models.CharField(
        max_length=50,
        choices=NotificationType.choices
    )
    message = models.CharField(max_length=255)
    link = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.notification_type} for {self.recipient.username}: {self.message}"
