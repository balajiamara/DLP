import os
import httpx
import logging
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied, NotFound, ValidationError
from django.shortcuts import get_object_or_404

logger = logging.getLogger(__name__)
FASTAPI_INTERNAL_URL = os.getenv("FASTAPI_INTERNAL_URL", "http://127.0.0.1:8001")

from django.db import transaction
from django.conf import settings
from classrooms.models import Classroom, ClassroomMembership
from syllabus.models import Topic, TopicProgress
from .models import Assignment, Submission, Quiz, Question, QuizAttempt, GeneratedDraft
from .serializers import (
    AssignmentSerializer,
    SubmissionSerializer,
    SubmissionFeedbackSerializer,
    QuizSerializer,
    QuizCreateSerializer,
    QuizDetailSerializer,
    QuizAttemptSerializer,
    GeneratedDraftSerializer,
    InternalDraftCreateSerializer
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


# --- Step 40: AI Generated Draft Views (Review-Before-Save Gate) ---

class ClassroomDraftListView(APIView):
    """
    List AI-generated drafts (quizzes or study plans) for a classroom.
    Teachers can see all drafts for the classroom.
    Students can only see study plan drafts where target_student is themselves.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, classroom_id):
        classroom = get_validated_classroom(request.user, classroom_id, require_teacher=False)
        is_teacher = (request.user == classroom.teacher)

        if is_teacher:
            queryset = classroom.generated_drafts.all()
        else:
            queryset = classroom.generated_drafts.filter(
                content_type=GeneratedDraft.ContentType.STUDY_PLAN,
                target_student=request.user
            )

        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter.upper())

        content_type_filter = request.query_params.get('content_type')
        if content_type_filter:
            queryset = queryset.filter(content_type=content_type_filter.upper())

        serializer = GeneratedDraftSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class DraftApproveView(APIView):
    """
    Approves a generated draft and converts it into real Quiz+Questions or Assignment records.
    Explicitly scoped to the classroom_id in the URL and gated to the classroom teacher.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, classroom_id, draft_id):
        classroom = get_validated_classroom(request.user, classroom_id, require_teacher=True)
        draft = get_object_or_404(GeneratedDraft, pk=draft_id, classroom=classroom)

        if draft.status != GeneratedDraft.Status.DRAFT:
            return Response(
                {"detail": f"Draft cannot be approved because it is already {draft.status.lower()}."},
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            if draft.content_type == GeneratedDraft.ContentType.QUIZ:
                content = draft.content
                title = content.get('title') or 'Generated Quiz'
                quiz = Quiz.objects.create(
                    classroom=classroom,
                    topic=draft.topic,
                    title=title,
                    created_by=request.user
                )

                questions_data = content.get('questions', [])
                for idx, q_data in enumerate(questions_data):
                    Question.objects.create(
                        quiz=quiz,
                        text=q_data['question'],
                        option_a=q_data['option_a'],
                        option_b=q_data['option_b'],
                        option_c=q_data['option_c'],
                        option_d=q_data['option_d'],
                        correct_option=q_data['correct_option'],
                        explanation=q_data.get('explanation', ''),
                        order=idx + 1
                    )

                draft.status = GeneratedDraft.Status.APPROVED
                draft.approved_quiz = quiz
                draft.save()

            elif draft.content_type == GeneratedDraft.ContentType.STUDY_PLAN:
                content = draft.content
                title = content.get('title') or 'Personalized Study Plan'
                overview = content.get('overview', '')
                tasks = content.get('tasks', [])
                task_lines = []
                for idx, t in enumerate(tasks, 1):
                    target = f" (Topic: {t.get('target_topic_name')})" if t.get('target_topic_name') else ""
                    pacing = f" [{t.get('suggested_pacing')}]" if t.get('suggested_pacing') else ""
                    due = f" Due: {t.get('suggested_due_date')}" if t.get('suggested_due_date') else ""
                    task_lines.append(f"{idx}. {t.get('title', 'Task')}{target}{pacing}{due}\n   {t.get('description', '')}")

                description = f"{overview}\n\nTasks:\n" + "\n".join(task_lines)
                assignment = Assignment.objects.create(
                    classroom=classroom,
                    topic=draft.topic,
                    title=title,
                    description=description.strip(),
                    created_by=request.user
                )

                draft.status = GeneratedDraft.Status.APPROVED
                draft.approved_assignment = assignment
                draft.save()

        serializer = GeneratedDraftSerializer(draft)
        return Response(serializer.data, status=status.HTTP_200_OK)


class DraftRejectView(APIView):
    """
    Rejects a generated draft without creating any live Quiz or Assignment records.
    Explicitly scoped to the classroom_id in the URL and gated to the classroom teacher.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, classroom_id, draft_id):
        classroom = get_validated_classroom(request.user, classroom_id, require_teacher=True)
        draft = get_object_or_404(GeneratedDraft, pk=draft_id, classroom=classroom)

        if draft.status != GeneratedDraft.Status.DRAFT:
            return Response(
                {"detail": f"Draft cannot be rejected because it is already {draft.status.lower()}."},
                status=status.HTTP_400_BAD_REQUEST
            )

        draft.status = GeneratedDraft.Status.REJECTED
        draft.save()

        serializer = GeneratedDraftSerializer(draft)
        return Response(serializer.data, status=status.HTTP_200_OK)


class InternalDraftCreateView(APIView):
    """
    Internal service-to-service endpoint for FastAPI to insert validated drafts
    into Django's database, respecting Django ORM constraints.
    Gated by X-Internal-Secret header.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        secret = request.headers.get("X-Internal-Secret", "")
        if not secret or secret != settings.INTERNAL_SERVICE_SECRET:
            return Response(
                {"detail": "Forbidden: Invalid internal service secret."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = InternalDraftCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        draft = serializer.save()
        return Response(GeneratedDraftSerializer(draft).data, status=status.HTTP_201_CREATED)


class DraftGenerateQuizProxyView(APIView):
    """
    Proxies AI quiz generation requests to FastAPI's internal /content/generate-quiz endpoint.
    Requires user authentication, enforces teacher-only access, attaches internal secret.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, classroom_id):
        classroom = get_validated_classroom(request.user, classroom_id, require_teacher=True)
        topic_id = request.data.get("topic_id")
        num_questions = request.data.get("num_questions", 5)

        if not topic_id:
            return Response(
                {"detail": "topic_id is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        target_url = f"{FASTAPI_INTERNAL_URL.rstrip('/')}/content/generate-quiz"
        payload = {
            "classroom_id": classroom.id,
            "topic_id": int(topic_id),
            "teacher_user_id": request.user.id,
            "num_questions": int(num_questions),
        }
        headers = {
            "X-Internal-Secret": settings.INTERNAL_SERVICE_SECRET,
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=45.0) as client:
                upstream_resp = client.post(target_url, json=payload, headers=headers)
                if upstream_resp.headers.get("content-type", "").startswith("application/json"):
                    data = upstream_resp.json()
                else:
                    data = {"detail": upstream_resp.text}

                # Intended validation errors (e.g. no approved material found for topic)
                if upstream_resp.status_code == status.HTTP_400_BAD_REQUEST:
                    detail_msg = data.get("detail") if isinstance(data, dict) else str(data)
                    return Response({"detail": detail_msg}, status=status.HTTP_400_BAD_REQUEST)

                # Prevent leaking internal 500s or unexpected upstream errors
                if upstream_resp.status_code >= 400:
                    logger.error("FastAPI returned error status %s for quiz generation: %s", upstream_resp.status_code, data)
                    return Response(
                        {"detail": "Content generation is currently unavailable. Please try again later."},
                        status=status.HTTP_502_BAD_GATEWAY
                    )

                return Response(data, status=upstream_resp.status_code)
        except Exception as exc:
            logger.error("Error proxying quiz generation to FastAPI: %s", exc)
            return Response(
                {"detail": "Content generation service is currently unavailable. Please try again later."},
                status=status.HTTP_502_BAD_GATEWAY
            )


class DraftGenerateStudyPlanProxyView(APIView):
    """
    Proxies AI study plan generation requests to FastAPI's internal /content/generate-study-plan endpoint.
    Requires user authentication (active classroom member), attaches internal secret.
    Students generate for themselves; teachers can generate for a target student.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, classroom_id):
        classroom = get_validated_classroom(request.user, classroom_id, require_teacher=False)
        is_teacher = (request.user == classroom.teacher)

        if is_teacher:
            student_user_id = request.data.get("student_user_id")
            if not student_user_id:
                return Response(
                    {"detail": "student_user_id is required for teacher-requested study plans."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            student_user_id = request.user.id

        goal_description = request.data.get("goal_description")
        deadline = request.data.get("deadline")

        if not goal_description:
            return Response(
                {"detail": "goal_description is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        target_url = f"{FASTAPI_INTERNAL_URL.rstrip('/')}/content/generate-study-plan"
        payload = {
            "classroom_id": classroom.id,
            "student_user_id": int(student_user_id),
            "requesting_user_id": request.user.id,
            "goal_description": goal_description,
            "deadline": deadline or None,
        }
        headers = {
            "X-Internal-Secret": settings.INTERNAL_SERVICE_SECRET,
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=45.0) as client:
                upstream_resp = client.post(target_url, json=payload, headers=headers)
                if upstream_resp.headers.get("content-type", "").startswith("application/json"):
                    data = upstream_resp.json()
                else:
                    data = {"detail": upstream_resp.text}

                # Intended validation errors (e.g. topic/progress validation)
                if upstream_resp.status_code == status.HTTP_400_BAD_REQUEST:
                    detail_msg = data.get("detail") if isinstance(data, dict) else str(data)
                    return Response({"detail": detail_msg}, status=status.HTTP_400_BAD_REQUEST)

                # Prevent leaking internal 500s or unexpected upstream errors
                if upstream_resp.status_code >= 400:
                    logger.error("FastAPI returned error status %s for study plan generation: %s", upstream_resp.status_code, data)
                    return Response(
                        {"detail": "Content generation is currently unavailable. Please try again later."},
                        status=status.HTTP_502_BAD_GATEWAY
                    )

                return Response(data, status=upstream_resp.status_code)
        except Exception as exc:
            logger.error("Error proxying study plan generation to FastAPI: %s", exc)
            return Response(
                {"detail": "Content generation service is currently unavailable. Please try again later."},
                status=status.HTTP_502_BAD_GATEWAY
            )




