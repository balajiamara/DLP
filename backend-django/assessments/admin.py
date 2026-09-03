from django.contrib import admin
from .models import Assignment, Submission, Quiz, Question, QuizAttempt


class SubmissionInline(admin.TabularInline):
    model = Submission
    extra = 0


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 1


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ('title', 'classroom', 'topic', 'due_date', 'created_by', 'created_at')
    list_filter = ('classroom', 'topic')
    search_fields = ('title', 'description')
    inlines = [SubmissionInline]


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ('assignment', 'student', 'grade', 'submitted_at')
    list_filter = ('assignment__classroom', 'assignment')
    search_fields = ('student__username', 'content', 'feedback')


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ('title', 'classroom', 'topic', 'created_by', 'created_at')
    list_filter = ('classroom', 'topic')
    search_fields = ('title',)
    inlines = [QuestionInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('quiz', 'order', 'text', 'correct_option')
    list_filter = ('quiz__classroom', 'quiz')
    search_fields = ('text',)


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ('quiz', 'student', 'score', 'attempted_at')
    list_filter = ('quiz__classroom', 'quiz')
    search_fields = ('student__username', 'quiz__title')
