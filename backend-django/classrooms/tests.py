from django.urls import reverse
from django.contrib.auth import get_user_model
from django.db.utils import IntegrityError
from rest_framework.test import APITestCase
from rest_framework import status

from .models import Classroom, ClassroomMembership, JoinToken

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
