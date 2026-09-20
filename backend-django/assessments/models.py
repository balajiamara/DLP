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
    explanation = models.TextField(blank=True, default='')

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


class GeneratedDraft(models.Model):
    """
    Holding area for LLM-generated content (quizzes and study plans).
    Content remains in DRAFT status until explicitly approved by a teacher,
    at which point it is converted into live Quiz or Assignment records.
    """
    class ContentType(models.TextChoices):
        QUIZ = 'QUIZ', 'Quiz'
        STUDY_PLAN = 'STUDY_PLAN', 'Study Plan'

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'

    classroom = models.ForeignKey(
        Classroom,
        on_delete=models.CASCADE,
        related_name='generated_drafts'
    )
    content_type = models.CharField(
        max_length=20,
        choices=ContentType.choices
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT
    )
    content = models.JSONField(
        help_text="Validated structured JSON output from LLM (syntax validated, factual correctness requires human review)."
    )
    topic = models.ForeignKey(
        Topic,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generated_drafts'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_drafts'
    )
    target_student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='target_study_plans'
    )
    requires_teacher_fact_check = models.BooleanField(
        default=True,
        help_text="Explicit indicator that schema validation confirms format only, not factual accuracy."
    )
    approved_quiz = models.OneToOneField(
        Quiz,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='origin_draft'
    )
    approved_assignment = models.OneToOneField(
        Assignment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='origin_draft'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.content_type} Draft ({self.status}) for {self.classroom.name} by {self.created_by.username}"

