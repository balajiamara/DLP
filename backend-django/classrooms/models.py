import secrets
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError


class Classroom(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='classrooms_taught'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        if self.teacher_id and self.teacher.role != 'TEACHER':
            raise ValidationError({'teacher': 'Assigned user must have the TEACHER role.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ClassroomMembership(models.Model):
    class RoleInClassroom(models.TextChoices):
        TEACHER = 'TEACHER', 'Teacher'
        STUDENT = 'STUDENT', 'Student'

    class MembershipStatus(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        REMOVED = 'REMOVED', 'Removed'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='classroom_memberships'
    )
    classroom = models.ForeignKey(
        Classroom,
        on_delete=models.CASCADE,
        related_name='memberships'
    )
    role_in_classroom = models.CharField(
        max_length=10,
        choices=RoleInClassroom.choices
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=10,
        choices=MembershipStatus.choices,
        default=MembershipStatus.ACTIVE
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'classroom'],
                name='unique_user_classroom_membership'
            )
        ]

    def __str__(self):
        return f"{self.user.username} in {self.classroom.name} ({self.role_in_classroom})"


def generate_join_token():
    return secrets.token_urlsafe(8)


class JoinToken(models.Model):
    classroom = models.ForeignKey(
        Classroom,
        on_delete=models.CASCADE,
        related_name='join_tokens'
    )
    token = models.CharField(
        max_length=64,
        unique=True,
        default=generate_join_token
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"JoinToken({self.token}) for {self.classroom.name}"
