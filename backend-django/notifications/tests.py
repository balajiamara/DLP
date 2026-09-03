from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase
from rest_framework import status

from classrooms.models import Classroom, ClassroomMembership
from syllabus.models import Course, Module, Topic
from doubts.models import Doubt, DoubtReply
from assessments.models import Assignment, Submission, Quiz
from .models import Notification

User = get_user_model()


class NotificationsAPITests(APITestCase):
    def setUp(self):
        # Teacher 1
        self.teacher1 = User.objects.create_user(
            email='teacher1@example.com',
            username='teacher1',
            password='Password123!',
            role='TEACHER'
        )
        self.classroom1 = Classroom.objects.create(
            name='Data Structures',
            description='Arrays, Trees, Graphs',
            teacher=self.teacher1
        )
        ClassroomMembership.objects.create(
            user=self.teacher1,
            classroom=self.classroom1,
            role_in_classroom='TEACHER',
            status=ClassroomMembership.MembershipStatus.ACTIVE
        )

        # Student 1
        self.student1 = User.objects.create_user(
            email='student1@example.com',
            username='student1',
            password='Password123!',
            role='STUDENT'
        )
        ClassroomMembership.objects.create(
            user=self.student1,
            classroom=self.classroom1,
            role_in_classroom='STUDENT',
            status=ClassroomMembership.MembershipStatus.ACTIVE
        )

        # Student 2
        self.student2 = User.objects.create_user(
            email='student2@example.com',
            username='student2',
            password='Password123!',
            role='STUDENT'
        )
        ClassroomMembership.objects.create(
            user=self.student2,
            classroom=self.classroom1,
            role_in_classroom='STUDENT',
            status=ClassroomMembership.MembershipStatus.ACTIVE
        )

        # Syllabus Topic
        self.course = Course.objects.create(classroom=self.classroom1, title='CS Course', order=1)
        self.module = Module.objects.create(course=self.course, title='Trees Module', order=1)
        self.topic = Topic.objects.create(module=self.module, title='Binary Search Trees', order=1)

    def test_user_only_sees_own_notifications(self):
        """User only sees their own notifications, never another user's."""
        n1 = Notification.objects.create(
            recipient=self.student1,
            notification_type=Notification.NotificationType.NEW_MATERIAL,
            message='Material for Student 1',
            link='/test/1'
        )
        n2 = Notification.objects.create(
            recipient=self.student2,
            notification_type=Notification.NotificationType.NEW_MATERIAL,
            message='Material for Student 2',
            link='/test/2'
        )

        self.client.force_authenticate(user=self.student1)
        res = self.client.get('/api/notifications/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        results = res.data['results'] if 'results' in res.data else res.data
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['id'], n1.id)

    def test_mark_single_notification_read_permissions(self):
        """Marking as read works; non-recipients get 403 Forbidden."""
        n1 = Notification.objects.create(
            recipient=self.student1,
            notification_type=Notification.NotificationType.DOUBT_REPLY,
            message='Someone replied to your doubt',
            link='/doubts/1'
        )

        # Student 2 tries to mark Student 1's notification read -> 403 Forbidden
        self.client.force_authenticate(user=self.student2)
        read_url = f'/api/notifications/{n1.id}/read/'
        res_forbidden = self.client.patch(read_url)
        self.assertEqual(res_forbidden.status_code, status.HTTP_403_FORBIDDEN)

        # Student 1 marks own notification read -> 200 OK
        self.client.force_authenticate(user=self.student1)
        res_ok = self.client.patch(read_url)
        self.assertEqual(res_ok.status_code, status.HTTP_200_OK)
        self.assertTrue(res_ok.data['is_read'])

    def test_mark_all_read_isolation(self):
        """mark-all-read only affects authenticated user's own notifications."""
        n1 = Notification.objects.create(recipient=self.student1, notification_type='NEW_QUIZ', message='Q1', link='/q/1')
        n2 = Notification.objects.create(recipient=self.student2, notification_type='NEW_QUIZ', message='Q2', link='/q/2')

        self.client.force_authenticate(user=self.student1)
        res = self.client.post('/api/notifications/mark-all-read/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        n1.refresh_from_db()
        n2.refresh_from_db()
        self.assertTrue(n1.is_read)
        self.assertFalse(n2.is_read)

        # Unread count check
        count_res = self.client.get('/api/notifications/unread-count/')
        self.assertEqual(count_res.data['unread_count'], 0)

    @patch('syllabus.views.upload_file')
    def test_material_creation_trigger(self, mock_upload):
        """Material creation triggers NEW_MATERIAL notifications for active classroom students."""
        self.client.force_authenticate(user=self.teacher1)
        pdf = SimpleUploadedFile("lecture.pdf", b"%PDF content", content_type="application/pdf")
        upload_url = f'/api/topics/{self.topic.id}/materials/'

        self.client.post(upload_url, {'file': pdf, 'title': 'BST Notes'}, format='multipart')

        # Check notifications generated for active students (Student 1 and Student 2)
        s1_notes = Notification.objects.filter(recipient=self.student1, notification_type='NEW_MATERIAL')
        s2_notes = Notification.objects.filter(recipient=self.student2, notification_type='NEW_MATERIAL')
        self.assertTrue(s1_notes.exists())
        self.assertTrue(s2_notes.exists())

    def test_doubt_reply_and_accepted_triggers(self):
        """Posting a doubt reply notifies author; accepting an answer notifies reply author."""
        doubt = Doubt.objects.create(classroom=self.classroom1, author=self.student1, title='BST Deletion', body='Help')

        # 1. Student 2 replies -> Student 1 gets DOUBT_REPLY notification
        self.client.force_authenticate(user=self.student2)
        reply_url = f'/api/classrooms/{self.classroom1.id}/doubts/{doubt.id}/replies/'
        rep_res = self.client.post(reply_url, {'body': 'Use successor replacement.'})
        reply_id = rep_res.data['id']

        s1_notes = Notification.objects.filter(recipient=self.student1, notification_type='DOUBT_REPLY')
        self.assertTrue(s1_notes.exists())

        # 2. Student 1 accepts answer -> Student 2 gets DOUBT_ACCEPTED notification
        self.client.force_authenticate(user=self.student1)
        accept_url = f'/api/classrooms/{self.classroom1.id}/doubts/{doubt.id}/replies/{reply_id}/accept/'
        self.client.patch(accept_url)

        s2_notes = Notification.objects.filter(recipient=self.student2, notification_type='DOUBT_ACCEPTED')
        self.assertTrue(s2_notes.exists())

    def test_assignment_quiz_and_grading_triggers(self):
        """Assignment creation, Quiz creation, and Submission grading trigger corresponding notifications."""
        self.client.force_authenticate(user=self.teacher1)
        base_url = f'/api/classrooms/{self.classroom1.id}'

        # 1. Teacher creates Assignment -> ASSIGNMENT_DUE_SOON notifications for students
        self.client.post(f'{base_url}/assignments/', {'title': 'Trees Assignment'})
        self.assertTrue(Notification.objects.filter(recipient=self.student1, notification_type='ASSIGNMENT_DUE_SOON').exists())

        # 2. Teacher creates Quiz -> NEW_QUIZ notifications for students
        self.client.post(f'{base_url}/quizzes/', {'title': 'Trees Quiz'})
        self.assertTrue(Notification.objects.filter(recipient=self.student1, notification_type='NEW_QUIZ').exists())

        # 3. Student 1 submits assignment
        assignment = Assignment.objects.first()
        self.client.force_authenticate(user=self.student1)
        sub_res = self.client.post(f'{base_url}/assignments/{assignment.id}/submit/', {'content': 'Tree solution'})
        sub_id = sub_res.data['id']

        # 4. Teacher grades submission -> ASSIGNMENT_GRADED notification for Student 1
        self.client.force_authenticate(user=self.teacher1)
        self.client.patch(f'/api/classrooms/{self.classroom1.id}/submissions/{sub_id}/feedback/', {'feedback': 'Well done!', 'grade': '100%'})
        self.assertTrue(Notification.objects.filter(recipient=self.student1, notification_type='ASSIGNMENT_GRADED').exists())
