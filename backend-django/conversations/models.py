from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError


class Conversation(models.Model):
    class Type(models.TextChoices):
        CLASSROOM = 'CLASSROOM', 'Classroom'
        GROUP = 'GROUP', 'Group'
        DIRECT = 'DIRECT', 'Direct'

    type = models.CharField(max_length=15, choices=Type.choices)
    classroom = models.ForeignKey(
        'classrooms.Classroom',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='conversation'
    )
    group = models.ForeignKey(
        'groups.Group',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='conversation'
    )
    user_a = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='direct_conversations_as_a'
    )
    user_b = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='direct_conversations_as_b'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            # Ensure at most 1 conversation per Classroom
            models.UniqueConstraint(
                fields=['classroom'],
                condition=models.Q(type='CLASSROOM'),
                name='unique_classroom_conversation'
            ),
            # Ensure at most 1 conversation per Group
            models.UniqueConstraint(
                fields=['group'],
                condition=models.Q(type='GROUP'),
                name='unique_group_conversation'
            ),
            # Ensure exactly 1 DM conversation between the same pair of users
            models.UniqueConstraint(
                fields=['user_a', 'user_b'],
                condition=models.Q(type='DIRECT'),
                name='unique_direct_conversation_pair'
            ),
            # DB-level canonical ordering guarantee: user_a < user_b
            models.CheckConstraint(
                condition=~models.Q(type='DIRECT') | models.Q(user_a_id__lt=models.F('user_b_id')),
                name='direct_user_a_lt_user_b'
            ),

        ]
        ordering = ['-updated_at']

    def clean(self):
        super().clean()
        if self.type == self.Type.CLASSROOM:
            if not self.classroom_id:
                raise ValidationError({'classroom': 'Classroom conversation must be linked to a classroom.'})
            if self.group_id or self.user_a_id or self.user_b_id:
                raise ValidationError('Classroom conversation cannot have group or direct participants.')
        elif self.type == self.Type.GROUP:
            if not self.group_id:
                raise ValidationError({'group': 'Group conversation must be linked to a group.'})
            if self.classroom_id or self.user_a_id or self.user_b_id:
                raise ValidationError('Group conversation cannot have classroom or direct participants.')
        elif self.type == self.Type.DIRECT:
            if not self.user_a_id or not self.user_b_id:
                raise ValidationError('Direct conversation requires both user_a and user_b.')
            if self.user_a_id == self.user_b_id:
                raise ValidationError('Cannot create a direct conversation with oneself.')
            if self.classroom_id or self.group_id:
                raise ValidationError('Direct conversation cannot have classroom or group.')
            # Normalize ordering so user_a_id < user_b_id
            if self.user_a_id > self.user_b_id:
                self.user_a_id, self.user_b_id = self.user_b_id, self.user_a_id

    def save(self, *args, **kwargs):
        if self.type == self.Type.DIRECT and self.user_a_id and self.user_b_id:
            if self.user_a_id > self.user_b_id:
                self.user_a_id, self.user_b_id = self.user_b_id, self.user_a_id
        super().save(*args, **kwargs)

    def __str__(self):
        if self.type == self.Type.CLASSROOM and self.classroom:
            return f"Classroom Conversation ({self.classroom.name})"
        if self.type == self.Type.GROUP and self.group:
            return f"Group Conversation ({self.group.name})"
        if self.type == self.Type.DIRECT and self.user_a and self.user_b:
            return f"DM ({self.user_a.username} <-> {self.user_b.username})"
        return f"Conversation {self.id} ({self.type})"


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_messages'
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Message {self.id} by {self.sender.username} in Conv {self.conversation_id}"
