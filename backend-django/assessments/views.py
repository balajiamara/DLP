from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied, NotFound, ValidationError
from django.shortcuts import get_object_or_404

from classrooms.models import Classroom, ClassroomMembership
from syllabus.models import Topic, TopicProgress
from .models import Assignment, Submission, Quiz, Question, QuizAttempt
from .serializers import (
    AssignmentSerializer,
    SubmissionSerializer,
    SubmissionFeedbackSerializer,
    QuizSerializer,
    QuizCreateSerializer,
    QuizDetailSerializer,
    QuizAttemptSerializer
)
from notifications.services import create_notification, notify_classroom_students
from notifications.models import Notification


def get_validated_classroom(user, classroom_id, require_teacher=False):
    """
    Validates that the classroom exists and the requesting user is an ACTIVE member of it.
    If not active member, raises NotFound (404) for privacy.
    If require_teacher=True and user is not assigned teacher, raises PermissionDenied (403).
    """
    classroom = get_object_or_404(Classroom, pk=classroom_id)
    is_active_member = classroom.memberships.filter(
        user=user,
        status=ClassroomMembership.MembershipStatus.ACTIVE
    ).exists()

    if not is_active_member:
        raise NotFound("Classroom not found.")

    if require_teacher and classroom.teacher != user:
        raise PermissionDenied("Only the classroom's teacher can perform this action.")

    return classroom


# --- Assignment Views ---

class AssignmentListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, classroom_id):
        classroom = get_validated_classroom(request.user, classroom_id, require_teacher=False)
        assignments = classroom.assignments.all()
        serializer = AssignmentSerializer(assignments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, classroom_id):
        classroom = get_validated_classroom(request.user, classroom_id, require_teacher=True)
        serializer = AssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        topic_obj = serializer.validated_data.get('topic')
        if topic_obj and topic_obj.module.course.classroom != classroom:
            raise ValidationError({'topic': 'Topic does not belong to this classroom.'})

        assignment = serializer.save(classroom=classroom, created_by=request.user)

        notify_classroom_students(
            classroom=classroom,
            notification_type=Notification.NotificationType.ASSIGNMENT_DUE_SOON,
            message=f"New assignment posted: {assignment.title}",
            link=f"/classrooms/{classroom.id}/assignments/{assignment.id}"
        )

        return Response(AssignmentSerializer(assignment).data, status=status.HTTP_201_CREATED)


class AssignmentDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, classroom_id, pk):
        classroom = get_validated_classroom(request.user, classroom_id, require_teacher=False)
        assignment = get_object_or_404(Assignment, pk=pk, classroom=classroom)
        serializer = AssignmentSerializer(assignment)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, classroom_id, pk):
        classroom = get_validated_classroom(request.user, classroom_id, require_teacher=True)
        assignment = get_object_or_404(Assignment, pk=pk, classroom=classroom)

        serializer = AssignmentSerializer(assignment, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated_assignment = serializer.save()
        return Response(AssignmentSerializer(updated_assignment).data, status=status.HTTP_200_OK)

    def delete(self, request, classroom_id, pk):
        classroom = get_validated_classroom(request.user, classroom_id, require_teacher=True)
        assignment = get_object_or_404(Assignment, pk=pk, classroom=classroom)
        assignment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# --- Submission Views ---

class SubmissionSubmitView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, classroom_id, assignment_id):
        classroom = get_validated_classroom(request.user, classroom_id, require_teacher=False)
        if request.user.role == 'TEACHER':
            raise PermissionDenied("Only students can submit assignments.")

        assignment = get_object_or_404(Assignment, pk=assignment_id, classroom=classroom)
        content = request.data.get('content', '')
        if not content:
            raise ValidationError({'content': 'Submission content is required.'})

        submission, created = Submission.objects.update_or_create(
            assignment=assignment,
            student=request.user,
            defaults={'content': content}
        )

        serializer = SubmissionSerializer(submission)
        http_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(serializer.data, status=http_status)


class AssignmentSubmissionsListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, classroom_id, assignment_id):
        classroom = get_validated_classroom(request.user, classroom_id, require_teacher=True)
        assignment = get_object_or_404(Assignment, pk=assignment_id, classroom=classroom)

        submissions = assignment.submissions.all()
        serializer = SubmissionSerializer(submissions, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class StudentSubmissionDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, classroom_id, assignment_id):
        classroom = get_validated_classroom(request.user, classroom_id, require_teacher=False)
        assignment = get_object_or_404(Assignment, pk=assignment_id, classroom=classroom)

        submission = get_object_or_404(Submission, assignment=assignment, student=request.user)
        serializer = SubmissionSerializer(submission)
        return Response(serializer.data, status=status.HTTP_200_OK)


class SubmissionFeedbackView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, classroom_id, pk):
        classroom = get_validated_classroom(request.user, classroom_id, require_teacher=True)
        submission = get_object_or_404(Submission, pk=pk, assignment__classroom=classroom)

        serializer = SubmissionFeedbackSerializer(submission, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated_submission = serializer.save()

        create_notification(
            recipient=submission.student,
            notification_type=Notification.NotificationType.ASSIGNMENT_GRADED,
            message=f"Your submission for '{submission.assignment.title}' has been graded",
            link=f"/classrooms/{classroom.id}/assignments/{submission.assignment.id}/my-submission"
        )

        return Response(SubmissionSerializer(updated_submission).data, status=status.HTTP_200_OK)


# --- Quiz Views ---

class QuizListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, classroom_id):
        classroom = get_validated_classroom(request.user, classroom_id, require_teacher=False)
        quizzes = classroom.quizzes.all()
        serializer = QuizSerializer(quizzes, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, classroom_id):
        classroom = get_validated_classroom(request.user, classroom_id, require_teacher=True)
        serializer = QuizCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        topic_obj = serializer.validated_data.get('topic')
        if topic_obj and topic_obj.module.course.classroom != classroom:
            raise ValidationError({'topic': 'Topic does not belong to this classroom.'})

        quiz = serializer.save(classroom=classroom, created_by=request.user)

        notify_classroom_students(
            classroom=classroom,
            notification_type=Notification.NotificationType.NEW_QUIZ,
            message=f"New quiz posted: {quiz.title}",
            link=f"/classrooms/{classroom.id}/quizzes/{quiz.id}"
        )

        return Response(QuizDetailSerializer(quiz, context={'request': request}).data, status=status.HTTP_201_CREATED)


class QuizDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, classroom_id, pk):
        classroom = get_validated_classroom(request.user, classroom_id, require_teacher=False)
        quiz = get_object_or_404(Quiz, pk=pk, classroom=classroom)
        serializer = QuizDetailSerializer(quiz, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, classroom_id, pk):
        classroom = get_validated_classroom(request.user, classroom_id, require_teacher=True)
        quiz = get_object_or_404(Quiz, pk=pk, classroom=classroom)

        serializer = QuizSerializer(quiz, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated_quiz = serializer.save()
        return Response(QuizDetailSerializer(updated_quiz, context={'request': request}).data, status=status.HTTP_200_OK)

    def delete(self, request, classroom_id, pk):
        classroom = get_validated_classroom(request.user, classroom_id, require_teacher=True)
        quiz = get_object_or_404(Quiz, pk=pk, classroom=classroom)
        quiz.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# --- Quiz Attempt & Server-Side Scoring Engine ---

class QuizAttemptCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, classroom_id, quiz_id):
        classroom = get_validated_classroom(request.user, classroom_id, require_teacher=False)
        if request.user.role == 'TEACHER':
            raise PermissionDenied("Teachers cannot attempt quizzes.")

        quiz = get_object_or_404(Quiz, pk=quiz_id, classroom=classroom)

        if QuizAttempt.objects.filter(quiz=quiz, student=request.user).exists():
            return Response({'detail': 'You have already attempted this quiz.'}, status=status.HTTP_400_BAD_REQUEST)

        answers = request.data.get('answers', {})
        questions = quiz.questions.all()
        total_questions = questions.count()
        correct_count = 0

        for q in questions:
            chosen = answers.get(str(q.id)) or answers.get(q.id)
            if chosen and str(chosen).strip().upper() == q.correct_option:
                correct_count += 1

        score_percentage = int(round((correct_count / total_questions * 100))) if total_questions > 0 else 0

        attempt = QuizAttempt.objects.create(
            quiz=quiz,
            student=request.user,
            answers=answers,
            score=score_percentage
        )

        # Update TopicProgress if quiz is tied to a topic
        if quiz.topic:
            target_state = (
                TopicProgress.LearningState.COMPLETED
                if score_percentage >= 70
                else TopicProgress.LearningState.PRACTICING
            )

            STATE_RANK = {
                TopicProgress.LearningState.NOT_STARTED: 0,
                TopicProgress.LearningState.LEARNING: 1,
                TopicProgress.LearningState.PRACTICING: 2,
                TopicProgress.LearningState.COMPLETED: 3,
                TopicProgress.LearningState.REVIEW_REQUIRED: 4,
                TopicProgress.LearningState.MASTERED: 5,
            }

            progress, created = TopicProgress.objects.get_or_create(
                student=request.user,
                topic=quiz.topic,
                defaults={'learning_state': target_state}
            )

            if not created:
                current_rank = STATE_RANK.get(progress.learning_state, 0)
                target_rank = STATE_RANK.get(target_state, 0)
                if target_rank > current_rank:
                    progress.learning_state = target_state
                    progress.save()

        return Response(QuizAttemptSerializer(attempt).data, status=status.HTTP_201_CREATED)


class StudentQuizAttemptDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, classroom_id, quiz_id):
        classroom = get_validated_classroom(request.user, classroom_id, require_teacher=False)
        quiz = get_object_or_404(Quiz, pk=quiz_id, classroom=classroom)

        attempt = get_object_or_404(QuizAttempt, quiz=quiz, student=request.user)
        serializer = QuizAttemptSerializer(attempt)
        return Response(serializer.data, status=status.HTTP_200_OK)


class QuizAttemptsListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, classroom_id, quiz_id):
        classroom = get_validated_classroom(request.user, classroom_id, require_teacher=True)
        quiz = get_object_or_404(Quiz, pk=quiz_id, classroom=classroom)

        attempts = quiz.attempts.all()
        serializer = QuizAttemptSerializer(attempts, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

