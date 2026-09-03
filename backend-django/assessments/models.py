from django.db import models
from django.conf import settings
from classrooms.models import Classroom
from syllabus.models import Topic


class Assignment(models.Model):
    classroom = models.ForeignKey(
        Classroom,
        on_delete=models.CASCADE,
        related_name='assignments'
    )
    topic = models.ForeignKey(
        Topic,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assignments'
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    due_date = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_assignments'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.classroom.name})"


class Submission(models.Model):
    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.CASCADE,
        related_name='submissions'
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='assignment_submissions'
    )
    content = models.TextField()
    submitted_at = models.DateTimeField(auto_now=True)
    feedback = models.TextField(null=True, blank=True)
    grade = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['assignment', 'student'],
                name='unique_assignment_student_submission'
            )
        ]

    def __str__(self):
        return f"{self.student.username}'s submission for {self.assignment.title}"


class Quiz(models.Model):
    classroom = models.ForeignKey(
        Classroom,
        on_delete=models.CASCADE,
        related_name='quizzes'
    )
    topic = models.ForeignKey(
        Topic,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='quizzes'
    )
    title = models.CharField(max_length=255)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_quizzes'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.classroom.name})"


class Question(models.Model):
    class CorrectOptionChoices(models.TextChoices):
        A = 'A', 'A'
        B = 'B', 'B'
        C = 'C', 'C'
        D = 'D', 'D'

    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name='questions'
    )
    text = models.TextField()
    option_a = models.CharField(max_length=255)
    option_b = models.CharField(max_length=255)
    option_c = models.CharField(max_length=255)
    option_d = models.CharField(max_length=255)
    correct_option = models.CharField(
        max_length=1,
        choices=CorrectOptionChoices.choices
    )
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f"Question {self.order} for {self.quiz.title}"


class QuizAttempt(models.Model):
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name='attempts'
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='quiz_attempts'
    )
    answers = models.JSONField(default=dict)
    score = models.IntegerField(default=0)
    attempted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['quiz', 'student'],
                name='unique_quiz_student_attempt'
            )
        ]

    def __str__(self):
        return f"{self.student.username}'s attempt on {self.quiz.title}: {self.score}%"
