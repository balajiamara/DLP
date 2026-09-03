from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status
from classrooms.models import Classroom, ClassroomMembership
from syllabus.models import Course, Module, Topic
from .models import Doubt, DoubtReply

User = get_user_model()


class DoubtsAPITests(APITestCase):
    def setUp(self):
        # Teacher 1 (Owner of Classroom 1)
        self.teacher1 = User.objects.create_user(
            email='teacher1@example.com',
            username='teacher1',
            password='Password123!',
            role='TEACHER'
        )
        self.classroom1 = Classroom.objects.create(
            name='Physics 101',
            description='Mechanics and Thermodynamics',
            teacher=self.teacher1
        )
        ClassroomMembership.objects.create(
            user=self.teacher1,
            classroom=self.classroom1,
            role_in_classroom='TEACHER',
            status=ClassroomMembership.MembershipStatus.ACTIVE
        )

        # Student 1 (Active member)
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

        # Student 2 (Active member)
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

        # Outsider student (Not a member)
        self.outsider_student = User.objects.create_user(
            email='outsider@example.com',
            username='outsider',
            password='Password123!',
            role='STUDENT'
        )

        # Syllabus Topic
        self.course = Course.objects.create(classroom=self.classroom1, title='Physics Course', order=1)
        self.module = Module.objects.create(course=self.course, title='Kinematics', order=1)
        self.topic = Topic.objects.create(module=self.module, title='Projectiles', order=1)

    def test_member_can_post_doubt_and_reply(self):
        """Active student 1 posts a doubt and active student 2 replies to it."""
        self.client.force_authenticate(user=self.student1)
        doubts_url = f'/api/classrooms/{self.classroom1.id}/doubts/'

        # 1. Post Doubt
        response = self.client.post(doubts_url, {
            'title': 'How to calculate launch angle?',
            'body': 'I am confused about projectile motion equations.',
            'topic': self.topic.id
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        doubt_id = response.data['id']
        self.assertEqual(response.data['author_username'], 'student1')

        # 2. Reply to Doubt as Student 2
        self.client.force_authenticate(user=self.student2)
        reply_url = f'/api/classrooms/{self.classroom1.id}/doubts/{doubt_id}/replies/'
        response = self.client.post(reply_url, {
            'body': 'Use theta = arctan(vy/vx).'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['author_username'], 'student2')

        # 3. GET Doubt Detail as Student 1
        self.client.force_authenticate(user=self.student1)
        detail_url = f'/api/classrooms/{self.classroom1.id}/doubts/{doubt_id}/'
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['replies']), 1)
        self.assertEqual(response.data['replies'][0]['body'], 'Use theta = arctan(vy/vx).')

    def test_non_member_receives_404_on_all_endpoints(self):
        """Non-members receive 404 Not Found on all doubt endpoints."""
        doubt = Doubt.objects.create(
            classroom=self.classroom1,
            author=self.student1,
            title='Private Question',
            body='Secret content'
        )
        reply = DoubtReply.objects.create(
            doubt=doubt,
            author=self.student1,
            body='Sample reply'
        )

        self.client.force_authenticate(user=self.outsider_student)
        base_url = f'/api/classrooms/{self.classroom1.id}/doubts/'

        self.assertEqual(self.client.get(base_url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.post(base_url, {'title': 'X', 'body': 'Y'}).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.get(f'{base_url}{doubt.id}/').status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.patch(f'{base_url}{doubt.id}/', {'title': 'Z'}).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.delete(f'{base_url}{doubt.id}/').status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.post(f'{base_url}{doubt.id}/replies/', {'body': 'R'}).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.patch(f'{base_url}{doubt.id}/replies/{reply.id}/accept/').status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.delete(f'{base_url}{doubt.id}/replies/{reply.id}/').status_code, status.HTTP_404_NOT_FOUND)

    def test_doubt_author_can_edit_own_doubt_others_forbidden(self):
        """Doubt author can edit title/body; another student gets 403 Forbidden."""
        doubt = Doubt.objects.create(
            classroom=self.classroom1,
            author=self.student1,
            title='Original Title',
            body='Original Body'
        )
        detail_url = f'/api/classrooms/{self.classroom1.id}/doubts/{doubt.id}/'

        # 1. Author Student 1 edits -> 200 OK
        self.client.force_authenticate(user=self.student1)
        response = self.client.patch(detail_url, {'title': 'Updated Title', 'body': 'Updated Body'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Updated Title')

        # 2. Student 2 attempts edit -> 403 Forbidden
        self.client.force_authenticate(user=self.student2)
        response = self.client.patch(detail_url, {'title': 'Hacked Title'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_doubt_author_can_accept_answer(self):
        """Doubt author accepts a reply, setting is_accepted_answer=True and parent is_resolved=True."""
        doubt = Doubt.objects.create(
            classroom=self.classroom1,
            author=self.student1,
            title='Vector Math Question',
            body='How to calculate dot product?'
        )
        reply = DoubtReply.objects.create(
            doubt=doubt,
            author=self.student2,
            body='Multiply components and sum them up.'
        )

        self.client.force_authenticate(user=self.student1)
        accept_url = f'/api/classrooms/{self.classroom1.id}/doubts/{doubt.id}/replies/{reply.id}/accept/'

        response = self.client.patch(accept_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_accepted_answer'])

        doubt.refresh_from_db()
        self.assertTrue(doubt.is_resolved)

    def test_classroom_teacher_can_accept_answer(self):
        """Classroom teacher can accept an answer on behalf of a student's doubt."""
        doubt = Doubt.objects.create(
            classroom=self.classroom1,
            author=self.student1,
            title='Thermodynamics Question',
            body='What is entropy?'
        )
        reply = DoubtReply.objects.create(
            doubt=doubt,
            author=self.student2,
            body='Entropy is a measure of molecular disorder.'
        )

        self.client.force_authenticate(user=self.teacher1)
        accept_url = f'/api/classrooms/{self.classroom1.id}/doubts/{doubt.id}/replies/{reply.id}/accept/'

        response = self.client.patch(accept_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_accepted_answer'])

        doubt.refresh_from_db()
        self.assertTrue(doubt.is_resolved)

    def test_unauthorized_student_cannot_accept_answer(self):
        """A random student who is not the author nor the teacher receives 403 when accepting an answer."""
        doubt = Doubt.objects.create(
            classroom=self.classroom1,
            author=self.student1,
            title='Kinematics Question',
            body='What is acceleration?'
        )
        reply = DoubtReply.objects.create(
            doubt=doubt,
            author=self.teacher1,
            body='Rate of change of velocity.'
        )

        # Authenticate as Student 2 (not author, not teacher)
        self.client.force_authenticate(user=self.student2)
        accept_url = f'/api/classrooms/{self.classroom1.id}/doubts/{doubt.id}/replies/{reply.id}/accept/'

        response = self.client.patch(accept_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_filtering_by_topic_and_resolved(self):
        """GET /doubts/ filtering by ?topic= and ?resolved= returns expected subsets."""
        d1 = Doubt.objects.create(classroom=self.classroom1, topic=self.topic, author=self.student1, title='Topic Question', body='Body 1', is_resolved=False)
        d2 = Doubt.objects.create(classroom=self.classroom1, topic=None, author=self.student2, title='General Question', body='Body 2', is_resolved=True)

        self.client.force_authenticate(user=self.student1)
        base_url = f'/api/classrooms/{self.classroom1.id}/doubts/'

        # Filter by ?topic=<id>
        res = self.client.get(f'{base_url}?topic={self.topic.id}')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]['id'], d1.id)

        # Filter by ?resolved=true
        res = self.client.get(f'{base_url}?resolved=true')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]['id'], d2.id)

        # Filter by ?resolved=false
        res = self.client.get(f'{base_url}?resolved=false')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]['id'], d1.id)

    def test_deletion_permissions(self):
        """Author and teacher can delete doubts and replies; unauthorized users get 403."""
        doubt = Doubt.objects.create(classroom=self.classroom1, author=self.student1, title='Doubt 1', body='Body')
        reply = DoubtReply.objects.create(doubt=doubt, author=self.student2, body='Reply 1')

        doubt_url = f'/api/classrooms/{self.classroom1.id}/doubts/{doubt.id}/'
        reply_url = f'/api/classrooms/{self.classroom1.id}/doubts/{doubt.id}/replies/{reply.id}/'

        # 1. Student 2 tries to delete Student 1's doubt -> 403 Forbidden
        self.client.force_authenticate(user=self.student2)
        self.assertEqual(self.client.delete(doubt_url).status_code, status.HTTP_403_FORBIDDEN)

        # 2. Student 1 tries to delete Student 2's reply -> 403 Forbidden
        self.client.force_authenticate(user=self.student1)
        self.assertEqual(self.client.delete(reply_url).status_code, status.HTTP_403_FORBIDDEN)

        # 3. Student 2 deletes their own reply -> 204 No Content
        self.client.force_authenticate(user=self.student2)
        self.assertEqual(self.client.delete(reply_url).status_code, status.HTTP_204_NO_CONTENT)

        # 4. Teacher deletes Student 1's doubt -> 204 No Content
        self.client.force_authenticate(user=self.teacher1)
        self.assertEqual(self.client.delete(doubt_url).status_code, status.HTTP_204_NO_CONTENT)
