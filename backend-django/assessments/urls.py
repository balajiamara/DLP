from django.urls import path
from .views import (
    AssignmentListCreateView,
    AssignmentDetailView,
    SubmissionSubmitView,
    AssignmentSubmissionsListView,
    StudentSubmissionDetailView,
    SubmissionFeedbackView,
    QuizListCreateView,
    QuizDetailView,
    QuizAttemptCreateView,
    StudentQuizAttemptDetailView,
    QuizAttemptsListView,
    ClassroomDraftListView,
    DraftApproveView,
    DraftRejectView,
    DraftGenerateQuizProxyView,
    DraftGenerateStudyPlanProxyView,
)

urlpatterns = [
    # Assignments
    path('assignments/', AssignmentListCreateView.as_view(), name='assignment_list_create'),
    path('assignments/<int:pk>/', AssignmentDetailView.as_view(), name='assignment_detail'),
    # Submissions
    path('assignments/<int:assignment_id>/submit/', SubmissionSubmitView.as_view(), name='submission_submit'),
    path('assignments/<int:assignment_id>/submissions/', AssignmentSubmissionsListView.as_view(), name='assignment_submissions_list'),
    path('assignments/<int:assignment_id>/my-submission/', StudentSubmissionDetailView.as_view(), name='student_submission_detail'),
    path('submissions/<int:pk>/feedback/', SubmissionFeedbackView.as_view(), name='submission_feedback'),
    # Quizzes
    path('quizzes/', QuizListCreateView.as_view(), name='quiz_list_create'),
    path('quizzes/<int:pk>/', QuizDetailView.as_view(), name='quiz_detail'),
    # Quiz Attempts
    path('quizzes/<int:quiz_id>/attempt/', QuizAttemptCreateView.as_view(), name='quiz_attempt_create'),
    path('quizzes/<int:quiz_id>/my-attempt/', StudentQuizAttemptDetailView.as_view(), name='student_quiz_attempt_detail'),
    path('quizzes/<int:quiz_id>/attempts/', QuizAttemptsListView.as_view(), name='quiz_attempts_list'),
    # AI Generated Drafts (Step 40 Review-Before-Save Gate)
    path('drafts/', ClassroomDraftListView.as_view(), name='draft_list'),
    path('drafts/<int:draft_id>/approve/', DraftApproveView.as_view(), name='draft_approve'),
    path('drafts/<int:draft_id>/reject/', DraftRejectView.as_view(), name='draft_reject'),
    path('drafts/generate-quiz/', DraftGenerateQuizProxyView.as_view(), name='draft_generate_quiz'),
    path('drafts/generate-study-plan/', DraftGenerateStudyPlanProxyView.as_view(), name='draft_generate_study_plan'),
]


