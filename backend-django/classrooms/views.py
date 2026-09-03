from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied, NotFound
from django.shortcuts import get_object_or_404

from django.db import models
from django.contrib.auth import get_user_model
from .models import Classroom, ClassroomMembership, JoinToken
from .serializers import ClassroomSerializer, ClassroomCreateSerializer
from .at_risk import get_student_at_risk_status
from syllabus.models import Topic, TopicProgress
from doubts.models import Doubt
from assessments.models import Submission, QuizAttempt

User = get_user_model()


class ClassroomListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ClassroomCreateSerializer
        return ClassroomSerializer

    def get_queryset(self):
        return Classroom.objects.filter(
            memberships__user=self.request.user,
            memberships__status=ClassroomMembership.MembershipStatus.ACTIVE
        ).distinct().order_by('-created_at')

    def create(self, request, *args, **kwargs):
        if request.user.role != 'TEACHER':
            raise PermissionDenied("Only teachers can create classrooms.")

        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        classroom = serializer.save()

        output_serializer = ClassroomSerializer(classroom, context={'request': request})
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


class ClassroomDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ClassroomSerializer

    def get_object(self):
        classroom_id = self.kwargs.get('pk')
        classroom = get_object_or_404(Classroom, pk=classroom_id)

        # Check if requesting user is an active member
        is_active_member = classroom.memberships.filter(
            user=self.request.user,
            status=ClassroomMembership.MembershipStatus.ACTIVE
        ).exists()

        if not is_active_member:
            raise NotFound("Classroom not found.")

        # For write operations (PATCH, PUT, DELETE), enforce owner/teacher permission
        if self.request.method in ['PATCH', 'PUT', 'DELETE']:
            if classroom.teacher != self.request.user:
                raise PermissionDenied("Only the classroom's assigned teacher can modify or delete this classroom.")

        return classroom


class CreateJoinTokenView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        classroom = get_object_or_404(Classroom, pk=pk)

        # Check if requesting user is an active member
        is_active_member = classroom.memberships.filter(
            user=request.user,
            status=ClassroomMembership.MembershipStatus.ACTIVE
        ).exists()

        if not is_active_member:
            raise NotFound("Classroom not found.")

        if classroom.teacher != request.user:
            raise PermissionDenied("Only the classroom's assigned teacher can generate join tokens.")

        join_token = JoinToken.objects.create(
            classroom=classroom,
            created_by=request.user
        )
        return Response(
            {
                'token': join_token.token,
                'classroom_id': classroom.id,
                'created_at': join_token.created_at
            },
            status=status.HTTP_201_CREATED
        )


class JoinClassroomView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, token):
        join_token = JoinToken.objects.filter(token=token).select_related('classroom').first()
        if not join_token:
            raise NotFound("Invalid or non-existent join token.")

        classroom = join_token.classroom
        membership, created = ClassroomMembership.objects.get_or_create(
            user=request.user,
            classroom=classroom,
            defaults={
                'role_in_classroom': request.user.role,
                'status': ClassroomMembership.MembershipStatus.ACTIVE
            }
        )

        if not created:
            if membership.status == ClassroomMembership.MembershipStatus.ACTIVE:
                return Response(
                    {
                        'detail': 'Already a member of this classroom.',
                        'classroom_id': classroom.id
                    },
                    status=status.HTTP_200_OK
                )
            else:
                membership.status = ClassroomMembership.MembershipStatus.ACTIVE
                membership.role_in_classroom = request.user.role
                membership.save()
                return Response(
                    {
                        'detail': 'Rejoined classroom successfully.',
                        'classroom_id': classroom.id
                    },
                    status=status.HTTP_200_OK
                )

        return Response(
            {
                'detail': 'Successfully joined classroom.',
                'classroom_id': classroom.id
            },
            status=status.HTTP_201_CREATED
        )


def get_teacher_validated_classroom(user, classroom_id):
    classroom = get_object_or_404(Classroom, pk=classroom_id)
    is_active_member = classroom.memberships.filter(
        user=user,
        status=ClassroomMembership.MembershipStatus.ACTIVE
    ).exists()

    if not is_active_member:
        raise NotFound("Classroom not found.")

    if classroom.teacher != user:
        raise PermissionDenied("Only the classroom's assigned teacher can access dashboard analytics.")

    return classroom


class ClassroomDashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, classroom_id):
        classroom = get_teacher_validated_classroom(request.user, classroom_id)

        # 1. Active Student Count
        active_student_memberships = ClassroomMembership.objects.filter(
            classroom=classroom,
            status=ClassroomMembership.MembershipStatus.ACTIVE,
            role_in_classroom='STUDENT'
        ).select_related('user')
        active_students = [m.user for m in active_student_memberships]
        active_student_count = len(active_students)

        # 2. Average Progress Percent
        topics = Topic.objects.filter(module__course__classroom=classroom).select_related('module')
        total_topics_count = topics.count()

        if total_topics_count == 0 or active_student_count == 0:
            average_progress_percent = 0.0
        else:
            student_percents = []
            for student in active_students:
                completed_count = TopicProgress.objects.filter(
                    student=student,
                    topic__in=topics,
                    learning_state__in=['COMPLETED', 'MASTERED']
                ).count()
                pct = round((completed_count / total_topics_count * 100), 1)
                student_percents.append(pct)
            average_progress_percent = round(sum(student_percents) / len(student_percents), 1) if student_percents else 0.0

        # 3. Topics By Completion
        topics_by_completion = []
        for t in topics:
            if active_student_count > 0:
                completed_count = TopicProgress.objects.filter(
                    topic=t,
                    student__in=active_students,
                    learning_state__in=['COMPLETED', 'MASTERED']
                ).count()
                rate = round((completed_count / active_student_count * 100), 1)
            else:
                completed_count = 0
                rate = 0.0

            topics_by_completion.append({
                'topic_id': t.id,
                'topic_title': t.title,
                'module_title': t.module.title,
                'completion_rate_percent': rate,
                'completed_students_count': completed_count,
                'total_active_students': active_student_count
            })

        # Sort topics_by_completion by completion_rate_percent ascending (lowest completion / hardest topics first)
        topics_by_completion.sort(key=lambda x: x['completion_rate_percent'])

        # 4. Doubt Stats
        doubts = Doubt.objects.filter(classroom=classroom)
        total_doubts = doubts.count()
        unresolved_doubts = doubts.filter(is_resolved=False).count()

        topic_doubts = (
            doubts.filter(topic__isnull=False)
            .values('topic__id', 'topic__title')
            .annotate(doubt_count=models.Count('id'))
            .order_by('-doubt_count')
        )
        most_doubted_topics = list(topic_doubts[:3])

        doubt_stats = {
            'total_doubts': total_doubts,
            'unresolved_doubts': unresolved_doubts,
            'most_doubted_topics': most_doubted_topics
        }

        # 5. Recent Activity Stream
        events = []

        recent_submissions = Submission.objects.filter(
            assignment__classroom=classroom
        ).select_related('student', 'assignment')[:10]
        for s in recent_submissions:
            events.append({
                'type': 'submission',
                'student_username': s.student.username,
                'description': f"Submitted '{s.assignment.title}'",
                'timestamp': s.submitted_at
            })

        recent_doubts = Doubt.objects.filter(
            classroom=classroom
        ).select_related('author')[:10]
        for d in recent_doubts:
            events.append({
                'type': 'doubt',
                'student_username': d.author.username,
                'description': f"Posted doubt: '{d.title}'",
                'timestamp': d.created_at
            })

        recent_attempts = QuizAttempt.objects.filter(
            quiz__classroom=classroom
        ).select_related('student', 'quiz')[:10]
        for a in recent_attempts:
            events.append({
                'type': 'quiz_attempt',
                'student_username': a.student.username,
                'description': f"Attempted quiz '{a.quiz.title}' (Score: {a.score}%)",
                'timestamp': a.attempted_at
            })

        events.sort(key=lambda x: x['timestamp'], reverse=True)
        recent_activity = events[:10]

        # 6. At-Risk Students Evaluation
        at_risk_students = []
        for st in active_students:
            status_info = get_student_at_risk_status(st, classroom, classroom_avg_percent=average_progress_percent)
            if status_info['at_risk']:
                at_risk_students.append({
                    'student_id': st.id,
                    'username': st.username,
                    'reasons': status_info['reasons']
                })

        return Response({
            'active_student_count': active_student_count,
            'average_progress_percent': average_progress_percent,
            'topics_by_completion': topics_by_completion,
            'doubt_stats': doubt_stats,
            'recent_activity': recent_activity,
            'at_risk_students': at_risk_students
        }, status=status.HTTP_200_OK)


class ClassroomStudentDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, classroom_id, student_id):
        classroom = get_teacher_validated_classroom(request.user, classroom_id)

        target_student = get_object_or_404(User, pk=student_id)
        is_active_student = classroom.memberships.filter(
            user=target_student,
            status=ClassroomMembership.MembershipStatus.ACTIVE,
            role_in_classroom='STUDENT'
        ).exists()

        if not is_active_student:
            raise NotFound("Student is not an active member of this classroom.")

        topics = Topic.objects.filter(module__course__classroom=classroom)
        total_topics_count = topics.count()

        completed_count = TopicProgress.objects.filter(
            student=target_student,
            topic__in=topics,
            learning_state__in=['COMPLETED', 'MASTERED']
        ).count()

        percent_complete = round((completed_count / total_topics_count * 100), 1) if total_topics_count > 0 else 0.0

        # Learning State Breakdown
        state_breakdown = {
            'NOT_STARTED': 0,
            'LEARNING': 0,
            'PRACTICING': 0,
            'COMPLETED': 0,
            'REVIEW_REQUIRED': 0,
            'MASTERED': 0,
        }

        progress_records = TopicProgress.objects.filter(
            student=target_student,
            topic__in=topics
        ).select_related('topic')

        recorded_topic_ids = set()
        for pr in progress_records:
            recorded_topic_ids.add(pr.topic.id)
            if pr.learning_state in state_breakdown:
                state_breakdown[pr.learning_state] += 1

        unrecorded_count = total_topics_count - len(recorded_topic_ids)
        if unrecorded_count > 0:
            state_breakdown['NOT_STARTED'] += unrecorded_count

        # Quiz Scores
        quiz_attempts = QuizAttempt.objects.filter(
            quiz__classroom=classroom,
            student=target_student
        ).select_related('quiz')

        quiz_scores = [
            {
                'quiz_id': a.quiz.id,
                'quiz_title': a.quiz.title,
                'score': a.score,
                'attempted_at': a.attempted_at
            }
            for a in quiz_attempts
        ]

        # Submissions
        submissions = Submission.objects.filter(
            assignment__classroom=classroom,
            student=target_student
        ).select_related('assignment')

        submission_history = [
            {
                'submission_id': s.id,
                'assignment_id': s.assignment.id,
                'assignment_title': s.assignment.title,
                'content': s.content,
                'feedback': s.feedback,
                'grade': s.grade,
                'submitted_at': s.submitted_at
            }
            for s in submissions
        ]

        # Doubts
        student_doubts = Doubt.objects.filter(
            classroom=classroom,
            author=target_student
        )

        doubts_posted = [
            {
                'doubt_id': d.id,
                'title': d.title,
                'is_resolved': d.is_resolved,
                'created_at': d.created_at
            }
            for d in student_doubts
        ]

        # At-Risk Evaluation
        at_risk_status = get_student_at_risk_status(target_student, classroom)

        return Response({
            'student_id': target_student.id,
            'student_username': target_student.username,
            'student_email': target_student.email,
            'percent_complete': percent_complete,
            'learning_state_breakdown': state_breakdown,
            'quiz_scores': quiz_scores,
            'submission_history': submission_history,
            'doubts_posted': doubts_posted,
            'at_risk': at_risk_status
        }, status=status.HTTP_200_OK)

