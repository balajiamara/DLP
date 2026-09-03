from datetime import timedelta
from django.utils import timezone
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.db.utils import IntegrityError
from rest_framework.test import APITestCase
from rest_framework import status

from .models import Classroom, ClassroomMembership, JoinToken
from syllabus.models import Course, Module, Topic, TopicProgress
from doubts.models import Doubt
from assessments.models import Assignment, Submission, Quiz, QuizAttempt

User = get_user_model()


class ClassroomTestCase(APITestCase):
    def setUp(self):
        self.teacher1 = User.objects.create_user(
            email='teacher1@example.com',
            username='teacher1',
            password='Password123!',
            role='TEACHER'
        )
        self.teacher2 = User.objects.create_user(
            email='teacher2@example.com',
            username='teacher2',
            password='Password123!',
            role='TEACHER'
        )
        self.student1 = User.objects.create_user(
            email='student1@example.com',
            username='student1',
            password='Password123!',
            role='STUDENT'
        )

        self.list_create_url = reverse('classroom_list_create')

    def test_teacher_can_create_classroom_and_becomes_first_member(self):
        """Test a user with TEACHER role can create a classroom and is auto-added as member."""
        self.client.force_authenticate(user=self.teacher1)
        payload = {
            'name': 'Python Batch 2026',
            'description': 'Advanced Python and Django course'
        }
        response = self.client.post(self.list_create_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Classroom.objects.count(), 1)

        classroom = Classroom.objects.get(pk=response.data['id'])
        self.assertEqual(classroom.teacher, self.teacher1)
        self.assertEqual(classroom.name, 'Python Batch 2026')

        # Check automatic membership creation
        self.assertEqual(classroom.memberships.count(), 1)
        membership = classroom.memberships.first()
        self.assertEqual(membership.user, self.teacher1)
        self.assertEqual(membership.role_in_classroom, ClassroomMembership.RoleInClassroom.TEACHER)
        self.assertEqual(membership.status, ClassroomMembership.MembershipStatus.ACTIVE)

    def test_student_cannot_create_classroom(self):
        """Test a user with STUDENT role cannot create a classroom (403 Forbidden)."""
        self.client.force_authenticate(user=self.student1)
        payload = {'name': 'Student Classroom Attempt'}
        response = self.client.post(self.list_create_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Classroom.objects.count(), 0)

    def test_user_only_sees_classrooms_they_are_active_member_of(self):
        """Test GET /api/classrooms/ only lists classrooms where user is an active member."""
        # Teacher 1 creates Classroom 1
        classroom1 = Classroom.objects.create(name='Classroom 1', teacher=self.teacher1)
        ClassroomMembership.objects.create(
            user=self.teacher1, classroom=classroom1, role_in_classroom='TEACHER', status='ACTIVE'
        )

        # Teacher 2 creates Classroom 2
        classroom2 = Classroom.objects.create(name='Classroom 2', teacher=self.teacher2)
        ClassroomMembership.objects.create(
            user=self.teacher2, classroom=classroom2, role_in_classroom='TEACHER', status='ACTIVE'
        )

        # Add Student 1 as member of Classroom 1 only
        ClassroomMembership.objects.create(
            user=self.student1, classroom=classroom1, role_in_classroom='STUDENT', status='ACTIVE'
        )

        # Student 1 requests list
        self.client.force_authenticate(user=self.student1)
        response = self.client.get(self.list_create_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data if isinstance(response.data, list) else response.data.get('results')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['id'], classroom1.id)

    def test_non_member_gets_404_on_classroom_detail(self):
        """Test a non-member gets 404 Not Found on classroom detail endpoint."""
        classroom = Classroom.objects.create(name='Private Classroom', teacher=self.teacher1)
        ClassroomMembership.objects.create(
            user=self.teacher1, classroom=classroom, role_in_classroom='TEACHER', status='ACTIVE'
        )

        detail_url = reverse('classroom_detail', kwargs={'pk': classroom.id})

        # Student 1 (non-member) requests detail
        self.client.force_authenticate(user=self.student1)
        response = self.client.get(detail_url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_only_classroom_own_teacher_can_edit_or_delete(self):
        """Test only the assigned teacher of the classroom can edit or delete it."""
        classroom = Classroom.objects.create(name='Original Name', teacher=self.teacher1)
        ClassroomMembership.objects.create(
            user=self.teacher1, classroom=classroom, role_in_classroom='TEACHER', status='ACTIVE'
        )

        # Add Teacher 2 as a member of Classroom (co-teacher / member)
        ClassroomMembership.objects.create(
            user=self.teacher2, classroom=classroom, role_in_classroom='TEACHER', status='ACTIVE'
        )

        detail_url = reverse('classroom_detail', kwargs={'pk': classroom.id})

        # Teacher 2 (member, but not the classroom's owner teacher) attempts PATCH -> 403 Forbidden
        self.client.force_authenticate(user=self.teacher2)
        patch_response = self.client.patch(detail_url, {'name': 'Hacked Name'}, format='json')
        self.assertEqual(patch_response.status_code, status.HTTP_403_FORBIDDEN)

        # Teacher 2 attempts DELETE -> 403 Forbidden
        delete_response = self.client.delete(detail_url)
        self.assertEqual(delete_response.status_code, status.HTTP_403_FORBIDDEN)

        # Teacher 1 (owner teacher) attempts PATCH -> 200 OK
        self.client.force_authenticate(user=self.teacher1)
        valid_patch = self.client.patch(detail_url, {'name': 'Updated Name'}, format='json')
        self.assertEqual(valid_patch.status_code, status.HTTP_200_OK)
        classroom.refresh_from_db()
        self.assertEqual(classroom.name, 'Updated Name')

        # Teacher 1 attempts DELETE -> 204 No Content
        valid_delete = self.client.delete(detail_url)
        self.assertEqual(valid_delete.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Classroom.objects.count(), 0)

    def test_duplicate_user_classroom_membership_rejected_at_db_level(self):
        """Test duplicate (user, classroom) membership is rejected by unique constraint."""
        classroom = Classroom.objects.create(name='Test Classroom', teacher=self.teacher1)
        ClassroomMembership.objects.create(
            user=self.student1, classroom=classroom, role_in_classroom='STUDENT', status='ACTIVE'
        )

        with self.assertRaises(IntegrityError):
            ClassroomMembership.objects.create(
                user=self.student1, classroom=classroom, role_in_classroom='STUDENT', status='ACTIVE'
            )

    def test_teacher_can_generate_join_token_for_own_classroom(self):
        """Test teacher can generate a join token for their own classroom."""
        classroom = Classroom.objects.create(name='Python 2026', teacher=self.teacher1)
        ClassroomMembership.objects.create(
            user=self.teacher1, classroom=classroom, role_in_classroom='TEACHER', status='ACTIVE'
        )

        join_link_url = reverse('create_join_token', kwargs={'pk': classroom.id})
        self.client.force_authenticate(user=self.teacher1)
        response = self.client.post(join_link_url)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('token', response.data)
        self.assertEqual(response.data['classroom_id'], classroom.id)
        self.assertEqual(JoinToken.objects.count(), 1)

    def test_non_owning_teacher_or_student_cannot_generate_join_token(self):
        """Test a student or non-owning teacher cannot generate a join token."""
        classroom = Classroom.objects.create(name='Python 2026', teacher=self.teacher1)
        ClassroomMembership.objects.create(
            user=self.teacher1, classroom=classroom, role_in_classroom='TEACHER', status='ACTIVE'
        )
        ClassroomMembership.objects.create(
            user=self.teacher2, classroom=classroom, role_in_classroom='TEACHER', status='ACTIVE'
        )

        join_link_url = reverse('create_join_token', kwargs={'pk': classroom.id})

        # Non-owning teacher member -> 403 Forbidden
        self.client.force_authenticate(user=self.teacher2)
        response_teacher2 = self.client.post(join_link_url)
        self.assertEqual(response_teacher2.status_code, status.HTTP_403_FORBIDDEN)

        # Student non-member -> 404 Not Found
        self.client.force_authenticate(user=self.student1)
        response_student = self.client.post(join_link_url)
        self.assertEqual(response_student.status_code, status.HTTP_404_NOT_FOUND)

    def test_student_can_join_classroom_using_valid_token(self):
        """Test student can join classroom using a valid join token."""
        classroom = Classroom.objects.create(name='Python 2026', teacher=self.teacher1)
        ClassroomMembership.objects.create(
            user=self.teacher1, classroom=classroom, role_in_classroom='TEACHER', status='ACTIVE'
        )
        token_obj = JoinToken.objects.create(classroom=classroom, created_by=self.teacher1)

        join_url = reverse('join_classroom', kwargs={'token': token_obj.token})
        self.client.force_authenticate(user=self.student1)
        response = self.client.post(join_url)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(ClassroomMembership.objects.filter(
            user=self.student1, classroom=classroom, status='ACTIVE', role_in_classroom='STUDENT'
        ).exists())

    def test_joining_with_invalid_or_nonexistent_token_returns_404(self):
        """Test joining with a non-existent token returns 404 Not Found."""
        join_url = reverse('join_classroom', kwargs={'token': 'invalid-token-xyz'})
        self.client.force_authenticate(user=self.student1)
        response = self.client.post(join_url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_joining_classroom_already_member_returns_200_no_duplicate(self):
        """Test joining a classroom user is already a member of returns 200 without creating duplicate."""
        classroom = Classroom.objects.create(name='Python 2026', teacher=self.teacher1)
        ClassroomMembership.objects.create(
            user=self.teacher1, classroom=classroom, role_in_classroom='TEACHER', status='ACTIVE'
        )
        ClassroomMembership.objects.create(
            user=self.student1, classroom=classroom, role_in_classroom='STUDENT', status='ACTIVE'
        )
        token_obj = JoinToken.objects.create(classroom=classroom, created_by=self.teacher1)

        join_url = reverse('join_classroom', kwargs={'token': token_obj.token})
        self.client.force_authenticate(user=self.student1)
        response = self.client.post(join_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('detail', response.data)
        self.assertEqual(ClassroomMembership.objects.filter(user=self.student1, classroom=classroom).count(), 1)

    # --- Analytics Dashboard & Student Drilldown Tests ---

    def test_teacher_sees_correct_aggregate_dashboard_numbers(self):
        """Teacher sees correct aggregate metrics for active student count, average progress, topic rates, doubts, and activity."""
        classroom = Classroom.objects.create(name='Data Science 101', teacher=self.teacher1)
        ClassroomMembership.objects.create(user=self.teacher1, classroom=classroom, role_in_classroom='TEACHER', status='ACTIVE')

        # Active Students
        s1 = self.student1
        s2 = User.objects.create_user(email='s2@example.com', username='student2', password='Password123!', role='STUDENT')
        ClassroomMembership.objects.create(user=s1, classroom=classroom, role_in_classroom='STUDENT', status='ACTIVE')
        ClassroomMembership.objects.create(user=s2, classroom=classroom, role_in_classroom='STUDENT', status='ACTIVE')

        # Course Hierarchy
        course = Course.objects.create(classroom=classroom, title='Data Analysis', order=1)
        module = Module.objects.create(course=course, title='Pandas', order=1)
        t1 = Topic.objects.create(module=module, title='DataFrames', order=1)
        t2 = Topic.objects.create(module=module, title='Series', order=2)

        # Progress: S1 completes both (100%), S2 completes T1 only (50%) -> Avg = 75.0%
        TopicProgress.objects.create(student=s1, topic=t1, learning_state='COMPLETED')
        TopicProgress.objects.create(student=s1, topic=t2, learning_state='MASTERED')
        TopicProgress.objects.create(student=s2, topic=t1, learning_state='COMPLETED')

        # Doubts
        d1 = Doubt.objects.create(classroom=classroom, topic=t1, author=s1, title='D1', body='B1', is_resolved=False)
        d2 = Doubt.objects.create(classroom=classroom, topic=None, author=s2, title='D2', body='B2', is_resolved=True)

        # Submissions & Quiz Attempts
        assign = Assignment.objects.create(classroom=classroom, title='Lab 1', created_by=self.teacher1)
        sub = Submission.objects.create(assignment=assign, student=s1, content='Pandas code')
        quiz = Quiz.objects.create(classroom=classroom, title='Quiz 1', created_by=self.teacher1)
        att = QuizAttempt.objects.create(quiz=quiz, student=s2, score=90)

        # Authenticate as Teacher 1
        self.client.force_authenticate(user=self.teacher1)
        dash_url = f'/api/classrooms/{classroom.id}/dashboard/'
        res = self.client.get(dash_url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.data
        self.assertEqual(data['active_student_count'], 2)
        self.assertEqual(data['average_progress_percent'], 75.0)

        # Doubt stats
        self.assertEqual(data['doubt_stats']['total_doubts'], 2)
        self.assertEqual(data['doubt_stats']['unresolved_doubts'], 1)
        self.assertEqual(len(data['doubt_stats']['most_doubted_topics']), 1)
        self.assertEqual(data['doubt_stats']['most_doubted_topics'][0]['topic__title'], 'DataFrames')

        # Recent activity
        self.assertGreaterEqual(len(data['recent_activity']), 3)

    def test_student_cannot_access_dashboard(self):
        """Student attempting to access classroom dashboard receives 403 Forbidden."""
        classroom = Classroom.objects.create(name='Physics', teacher=self.teacher1)
        ClassroomMembership.objects.create(user=self.teacher1, classroom=classroom, role_in_classroom='TEACHER', status='ACTIVE')
        ClassroomMembership.objects.create(user=self.student1, classroom=classroom, role_in_classroom='STUDENT', status='ACTIVE')

        self.client.force_authenticate(user=self.student1)
        dash_url = f'/api/classrooms/{classroom.id}/dashboard/'
        response = self.client.get(dash_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_different_teacher_gets_404_on_dashboard(self):
        """A teacher from another classroom gets 404 Not Found on dashboard."""
        classroom = Classroom.objects.create(name='Chemistry', teacher=self.teacher1)
        ClassroomMembership.objects.create(user=self.teacher1, classroom=classroom, role_in_classroom='TEACHER', status='ACTIVE')

        self.client.force_authenticate(user=self.teacher2)
        dash_url = f'/api/classrooms/{classroom.id}/dashboard/'
        response = self.client.get(dash_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_student_drilldown_returns_correct_data_and_404_for_non_member(self):
        """Student drilldown endpoint returns student's progress and history, and 404s for non-members."""
        classroom = Classroom.objects.create(name='Maths', teacher=self.teacher1)
        ClassroomMembership.objects.create(user=self.teacher1, classroom=classroom, role_in_classroom='TEACHER', status='ACTIVE')
        ClassroomMembership.objects.create(user=self.student1, classroom=classroom, role_in_classroom='STUDENT', status='ACTIVE')

        course = Course.objects.create(classroom=classroom, title='Algebra', order=1)
        module = Module.objects.create(course=course, title='Polynomials', order=1)
        t1 = Topic.objects.create(module=module, title='Quadratic', order=1)

        TopicProgress.objects.create(student=self.student1, topic=t1, learning_state='COMPLETED')

        self.client.force_authenticate(user=self.teacher1)

        # 1. Valid active student drilldown -> 200 OK
        detail_url = f'/api/classrooms/{classroom.id}/students/{self.student1.id}/detail/'
        res = self.client.get(detail_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['percent_complete'], 100.0)
        self.assertEqual(res.data['learning_state_breakdown']['COMPLETED'], 1)

        # 2. Non-member student drilldown -> 404 Not Found
        non_member_student = User.objects.create_user(email='other@example.com', username='other', password='Password123!', role='STUDENT')
        invalid_url = f'/api/classrooms/{classroom.id}/students/{non_member_student.id}/detail/'
        res_404 = self.client.get(invalid_url)
        self.assertEqual(res_404.status_code, status.HTTP_404_NOT_FOUND)

    # --- Explainable At-Risk Signal Tests ---

    def test_student_inactive_and_behind_pace_flagged_at_risk(self):
        """A student with no activity for 4+ days AND behind pace is flagged as at-risk with explainable reasons."""
        classroom = Classroom.objects.create(name='AI Foundations', teacher=self.teacher1)
        ClassroomMembership.objects.create(user=self.teacher1, classroom=classroom, role_in_classroom='TEACHER', status='ACTIVE')

        six_days_ago = timezone.now() - timedelta(days=6)

        s1_mem = ClassroomMembership.objects.create(user=self.student1, classroom=classroom, role_in_classroom='STUDENT', status='ACTIVE')
        ClassroomMembership.objects.filter(pk=s1_mem.pk).update(joined_at=six_days_ago)

        s2 = User.objects.create_user(email='s2_smart@example.com', username='s2_smart', password='Password123!', role='STUDENT')
        ClassroomMembership.objects.create(user=s2, classroom=classroom, role_in_classroom='STUDENT', status='ACTIVE')

        course = Course.objects.create(classroom=classroom, title='Neural Nets', order=1)
        module = Module.objects.create(course=course, title='Backprop', order=1)
        t1 = Topic.objects.create(module=module, title='Gradient Descent', order=1)
        t2 = Topic.objects.create(module=module, title='Loss Functions', order=2)

        # Student 2 completes both topics today -> Avg progress = 50%
        TopicProgress.objects.create(student=s2, topic=t1, learning_state='COMPLETED')
        TopicProgress.objects.create(student=s2, topic=t2, learning_state='MASTERED')

        # Student 1 has 0 progress and last activity 6 days ago
        tp_s1 = TopicProgress.objects.create(student=self.student1, topic=t1, learning_state='NOT_STARTED')
        TopicProgress.objects.filter(pk=tp_s1.pk).update(updated_at=six_days_ago)

        from classrooms.at_risk import get_student_at_risk_status
        status_info = get_student_at_risk_status(self.student1, classroom)

        self.assertTrue(status_info['at_risk'])
        self.assertGreaterEqual(status_info['no_activity_days'], 6)
        self.assertTrue(any('No activity' in r for r in status_info['reasons']))
        self.assertTrue(any('behind classroom average' in r for r in status_info['reasons']))

    def test_inactivity_alone_is_not_sufficient_to_flag_at_risk(self):
        """A student inactive for 4+ days but 100% on pace and good quiz average is NOT flagged."""
        classroom = Classroom.objects.create(name='Robotics', teacher=self.teacher1)
        ClassroomMembership.objects.create(user=self.teacher1, classroom=classroom, role_in_classroom='TEACHER', status='ACTIVE')

        six_days_ago = timezone.now() - timedelta(days=6)
        s1_mem = ClassroomMembership.objects.create(user=self.student1, classroom=classroom, role_in_classroom='STUDENT', status='ACTIVE')
        ClassroomMembership.objects.filter(pk=s1_mem.pk).update(joined_at=six_days_ago)

        course = Course.objects.create(classroom=classroom, title='Sensors', order=1)
        module = Module.objects.create(course=course, title='LIDAR', order=1)
        t1 = Topic.objects.create(module=module, title='Point Clouds', order=1)

        # Student 1 completed everything 6 days ago (100% progress)
        tp = TopicProgress.objects.create(student=self.student1, topic=t1, learning_state='MASTERED')
        TopicProgress.objects.filter(pk=tp.pk).update(updated_at=six_days_ago)

        quiz = Quiz.objects.create(classroom=classroom, title='LIDAR Quiz', created_by=self.teacher1)
        qa = QuizAttempt.objects.create(quiz=quiz, student=self.student1, score=95)
        QuizAttempt.objects.filter(pk=qa.pk).update(attempted_at=six_days_ago)

        from classrooms.at_risk import get_student_at_risk_status
        status_info = get_student_at_risk_status(self.student1, classroom)

        self.assertFalse(status_info['at_risk'])

    def test_behind_pace_alone_is_not_sufficient_to_flag_at_risk(self):
        """A student behind pace who was active yesterday is NOT flagged as at-risk."""
        classroom = Classroom.objects.create(name='Linear Algebra', teacher=self.teacher1)
        ClassroomMembership.objects.create(user=self.teacher1, classroom=classroom, role_in_classroom='TEACHER', status='ACTIVE')

        ClassroomMembership.objects.create(user=self.student1, classroom=classroom, role_in_classroom='STUDENT', status='ACTIVE')
        s2 = User.objects.create_user(email='s2_fast@example.com', username='s2_fast', password='Password123!', role='STUDENT')
        ClassroomMembership.objects.create(user=s2, classroom=classroom, role_in_classroom='STUDENT', status='ACTIVE')

        course = Course.objects.create(classroom=classroom, title='Matrices', order=1)
        module = Module.objects.create(course=course, title='Eigenvalues', order=1)
        t1 = Topic.objects.create(module=module, title='Vectors', order=1)

        # Student 2 completes topic -> Classroom avg = 50%
        TopicProgress.objects.create(student=s2, topic=t1, learning_state='COMPLETED')

        # Student 1 was active yesterday (1 day ago), even though progress is 0%
        yesterday = timezone.now() - timedelta(days=1)
        tp = TopicProgress.objects.create(student=self.student1, topic=t1, learning_state='LEARNING')
        TopicProgress.objects.filter(pk=tp.pk).update(updated_at=yesterday)

        from classrooms.at_risk import get_student_at_risk_status
        status_info = get_student_at_risk_status(self.student1, classroom)

        self.assertFalse(status_info['at_risk'])
        self.assertLess(status_info['no_activity_days'], 4)

    def test_no_quiz_attempts_does_not_cause_false_positive(self):
        """A student with no quiz attempts does not get falsely flagged for low quiz average."""
        classroom = Classroom.objects.create(name='Stats', teacher=self.teacher1)
        ClassroomMembership.objects.create(user=self.teacher1, classroom=classroom, role_in_classroom='TEACHER', status='ACTIVE')
        ClassroomMembership.objects.create(user=self.student1, classroom=classroom, role_in_classroom='STUDENT', status='ACTIVE')

        six_days_ago = timezone.now() - timedelta(days=6)

        course = Course.objects.create(classroom=classroom, title='Probability', order=1)
        module = Module.objects.create(course=course, title='Distributions', order=1)
        t1 = Topic.objects.create(module=module, title='Normal Distribution', order=1)

        # Student 1 completed topic 6 days ago
        tp = TopicProgress.objects.create(student=self.student1, topic=t1, learning_state='COMPLETED')
        TopicProgress.objects.filter(pk=tp.pk).update(updated_at=six_days_ago)

        from classrooms.at_risk import get_student_at_risk_status
        status_info = get_student_at_risk_status(self.student1, classroom)

        self.assertFalse(status_info['at_risk'])
        self.assertFalse(any('Low quiz average' in r for r in status_info['reasons']))

    def test_dashboard_at_risk_students_list_filtering(self):
        """Dashboard's at_risk_students array correctly includes only the flagged at-risk students."""
        classroom = Classroom.objects.create(name='Algorithms 2026', teacher=self.teacher1)
        ClassroomMembership.objects.create(user=self.teacher1, classroom=classroom, role_in_classroom='TEACHER', status='ACTIVE')

        six_days_ago = timezone.now() - timedelta(days=6)

        # Student 1 (At-Risk: inactive 6 days & 0% progress)
        s1_mem = ClassroomMembership.objects.create(user=self.student1, classroom=classroom, role_in_classroom='STUDENT', status='ACTIVE')
        ClassroomMembership.objects.filter(pk=s1_mem.pk).update(joined_at=six_days_ago)

        # Student 2 (On-track)
        s2 = User.objects.create_user(email='s2_good@example.com', username='s2_good', password='Password123!', role='STUDENT')
        ClassroomMembership.objects.create(user=s2, classroom=classroom, role_in_classroom='STUDENT', status='ACTIVE')

        course = Course.objects.create(classroom=classroom, title='Graph Theory', order=1)
        module = Module.objects.create(course=course, title='Dijkstra', order=1)
        t1 = Topic.objects.create(module=module, title='Shortest Path', order=1)

        TopicProgress.objects.create(student=s2, topic=t1, learning_state='COMPLETED')
        tp1 = TopicProgress.objects.create(student=self.student1, topic=t1, learning_state='NOT_STARTED')
        TopicProgress.objects.filter(pk=tp1.pk).update(updated_at=six_days_ago)

        self.client.force_authenticate(user=self.teacher1)
        dash_url = f'/api/classrooms/{classroom.id}/dashboard/'
        res = self.client.get(dash_url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        at_risk_list = res.data['at_risk_students']
        self.assertEqual(len(at_risk_list), 1)
        self.assertEqual(at_risk_list[0]['student_id'], self.student1.id)
        self.assertEqual(at_risk_list[0]['username'], 'student1')


