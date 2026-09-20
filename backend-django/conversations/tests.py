from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from django.utils import timezone
from datetime import timedelta

from classrooms.models import Classroom, ClassroomMembership
from groups.models import Group, GroupMembership
from conversations.models import Conversation, Message
import importlib
backfill_module = importlib.import_module('conversations.migrations.0002_backfill_conversations')
backfill_conversations = backfill_module.backfill_conversations
from django.apps import apps

User = get_user_model()


class ConversationModelConstraintTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            username='model_teacher',
            email='model_teacher@example.com',
            password='password123',
            role='TEACHER'
        )
        self.user1 = User.objects.create_user(
            username='model_user1',
            email='model_user1@example.com',
            password='password123',
            role='STUDENT'
        )
        self.user2 = User.objects.create_user(
            username='model_user2',
            email='model_user2@example.com',
            password='password123',
            role='STUDENT'
        )
        self.user3 = User.objects.create_user(
            username='model_user3',
            email='model_user3@example.com',
            password='password123',
            role='STUDENT'
        )
        self.classroom = Classroom.objects.create(name='Math 101', teacher=self.teacher)
        self.group1 = Group.objects.create(name='Study Group 1', created_by=self.user1)
        self.group2 = Group.objects.create(name='Study Group 2', created_by=self.user2)

    def test_partial_unique_constraints_behave_correctly_with_null_values_across_types(self):
        """
        Explicit test proving partial unique constraints allow multiple records with NULL values:
        Create two GROUP-type conversations and two DIRECT-type conversations (different user pairs)
        in the same test, and confirm none violate unique_classroom_conversation or
        unique_group_conversation just because they share classroom=NULL or group=NULL.
        """
        # Ensure conversations for group1 and group2 exist
        conv_group1, _ = Conversation.objects.get_or_create(group=self.group1, type=Conversation.Type.GROUP)
        conv_group2, _ = Conversation.objects.get_or_create(group=self.group2, type=Conversation.Type.GROUP)

        # Both have classroom=None
        self.assertIsNone(conv_group1.classroom)
        self.assertIsNone(conv_group2.classroom)

        # Create two separate DIRECT conversations (both have classroom=None and group=None)
        u1, u2 = sorted([self.user1.id, self.user2.id])
        u2_b, u3 = sorted([self.user2.id, self.user3.id])

        conv_dm1 = Conversation.objects.create(
            type=Conversation.Type.DIRECT,
            user_a_id=u1,
            user_b_id=u2
        )
        conv_dm2 = Conversation.objects.create(
            type=Conversation.Type.DIRECT,
            user_a_id=u2_b,
            user_b_id=u3
        )

        self.assertIsNone(conv_dm1.classroom)
        self.assertIsNone(conv_dm1.group)
        self.assertIsNone(conv_dm2.classroom)
        self.assertIsNone(conv_dm2.group)

        # All 4 conversations exist simultaneously without constraint conflicts
        self.assertEqual(
            Conversation.objects.filter(id__in=[conv_group1.id, conv_group2.id, conv_dm1.id, conv_dm2.id]).count(),
            4
        )

    def test_unique_classroom_conversation_constraint(self):
        """Test at most 1 conversation can exist for a Classroom."""
        Conversation.objects.get_or_create(classroom=self.classroom, type=Conversation.Type.CLASSROOM)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Conversation.objects.create(classroom=self.classroom, type=Conversation.Type.CLASSROOM)

    def test_unique_group_conversation_constraint(self):
        """Test at most 1 conversation can exist for a Group."""
        Conversation.objects.get_or_create(group=self.group1, type=Conversation.Type.GROUP)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Conversation.objects.create(group=self.group1, type=Conversation.Type.GROUP)

    def test_direct_conversation_uniqueness_and_ordering(self):
        """Test duplicate DM pairs cannot be created regardless of user order."""
        u1, u2 = sorted([self.user1.id, self.user2.id])
        conv = Conversation.objects.create(
            type=Conversation.Type.DIRECT,
            user_a_id=u1,
            user_b_id=u2
        )
        self.assertEqual(conv.user_a_id, u1)
        self.assertEqual(conv.user_b_id, u2)

        # Attempting to create duplicate (u1, u2) violates unique constraint
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Conversation.objects.create(
                    type=Conversation.Type.DIRECT,
                    user_a_id=u1,
                    user_b_id=u2
                )

        # Direct DB insert violating check constraint (user_a >= user_b)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                # Direct bulk insert bypassing save() to test DB-level CheckConstraint
                Conversation.objects.bulk_create([
                    Conversation(
                        type=Conversation.Type.DIRECT,
                        user_a_id=u2,
                        user_b_id=u1
                    )
                ])


class AutoProvisioningAndBackfillTests(APITestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            username='ap_teacher',
            email='ap_teacher@example.com',
            password='password123',
            role='TEACHER'
        )
        self.student = User.objects.create_user(
            username='ap_student',
            email='ap_student@example.com',
            password='password123',
            role='STUDENT'
        )

    def test_classroom_creation_auto_provisions_conversation(self):
        """Creating a Classroom via API creates its Conversation in the same transaction."""
        self.client.force_authenticate(user=self.teacher)
        resp = self.client.post('/api/classrooms/', {
            'name': 'Auto-provisioned Class',
            'description': 'Testing auto provisioning'
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        classroom_id = resp.data['id']

        conv = Conversation.objects.filter(classroom_id=classroom_id, type=Conversation.Type.CLASSROOM).first()
        self.assertIsNotNone(conv)
        self.assertEqual(conv.classroom_id, classroom_id)

    def test_group_creation_auto_provisions_conversation(self):
        """Creating a Group via API creates its Conversation in the same transaction."""
        self.client.force_authenticate(user=self.student)
        resp = self.client.post('/api/groups/', {
            'name': 'Auto-provisioned Group',
            'description': 'Testing auto provisioning'
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        group_id = resp.data['id']

        conv = Conversation.objects.filter(group_id=group_id, type=Conversation.Type.GROUP).first()
        self.assertIsNotNone(conv)
        self.assertEqual(conv.group_id, group_id)

    def test_backfill_migration_is_idempotent(self):
        """Backfill migration provisions missing conversations and does not duplicate on re-run."""
        # Create unprovisioned classroom and group directly
        c = Classroom.objects.create(name='Unprovisioned Class', teacher=self.teacher)
        g = Group.objects.create(name='Unprovisioned Group', created_by=self.student)

        # Delete any conversation created by serializers/signals if any
        Conversation.objects.filter(classroom=c).delete()
        Conversation.objects.filter(group=g).delete()

        self.assertFalse(Conversation.objects.filter(classroom=c).exists())
        self.assertFalse(Conversation.objects.filter(group=g).exists())

        # Run backfill
        backfill_conversations(apps, None)

        self.assertTrue(Conversation.objects.filter(classroom=c).exists())
        self.assertTrue(Conversation.objects.filter(group=g).exists())
        count_c = Conversation.objects.filter(classroom=c).count()
        count_g = Conversation.objects.filter(group=g).count()
        self.assertEqual(count_c, 1)
        self.assertEqual(count_g, 1)

        # Run backfill again (Idempotency test)
        backfill_conversations(apps, None)
        self.assertEqual(Conversation.objects.filter(classroom=c).count(), 1)
        self.assertEqual(Conversation.objects.filter(group=g).count(), 1)


class ConversationAuthorizationAndAPITests(APITestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            username='auth_teacher',
            email='auth_teacher@example.com',
            password='password123',
            role='TEACHER'
        )
        self.student_active = User.objects.create_user(
            username='student_active',
            email='student_active@example.com',
            password='password123',
            role='STUDENT'
        )
        self.student_removed = User.objects.create_user(
            username='student_removed',
            email='student_removed@example.com',
            password='password123',
            role='STUDENT'
        )
        self.student_outsider = User.objects.create_user(
            username='student_outsider',
            email='student_outsider@example.com',
            password='password123',
            role='STUDENT'
        )

        # Classroom & Memberships
        self.classroom = Classroom.objects.create(name='Physics 201', teacher=self.teacher)
        ClassroomMembership.objects.create(
            user=self.teacher,
            classroom=self.classroom,
            role_in_classroom=ClassroomMembership.RoleInClassroom.TEACHER,
            status=ClassroomMembership.MembershipStatus.ACTIVE
        )
        ClassroomMembership.objects.create(
            user=self.student_active,
            classroom=self.classroom,
            role_in_classroom=ClassroomMembership.RoleInClassroom.STUDENT,
            status=ClassroomMembership.MembershipStatus.ACTIVE
        )
        ClassroomMembership.objects.create(
            user=self.student_removed,
            classroom=self.classroom,
            role_in_classroom=ClassroomMembership.RoleInClassroom.STUDENT,
            status=ClassroomMembership.MembershipStatus.REMOVED
        )
        self.conv_classroom, _ = Conversation.objects.get_or_create(
            classroom=self.classroom,
            type=Conversation.Type.CLASSROOM
        )

        # Group & Memberships
        self.group = Group.objects.create(name='Lab Team Alpha', created_by=self.student_active)
        GroupMembership.objects.create(
            user=self.student_active,
            group=self.group,
            status=GroupMembership.MembershipStatus.ACTIVE
        )
        GroupMembership.objects.create(
            user=self.student_removed,
            group=self.group,
            status=GroupMembership.MembershipStatus.REMOVED
        )
        self.conv_group, _ = Conversation.objects.get_or_create(
            group=self.group,
            type=Conversation.Type.GROUP
        )

        # Direct Conversation between student_active and teacher
        u1, u2 = sorted([self.student_active.id, self.teacher.id])
        self.conv_direct = Conversation.objects.create(
            type=Conversation.Type.DIRECT,
            user_a_id=u1,
            user_b_id=u2
        )

    def test_classroom_conversation_authorization(self):
        """Active members can read/post; removed members and outsiders receive 404."""
        # 1. Active member sends message -> 201
        self.client.force_authenticate(user=self.student_active)
        resp = self.client.post(f'/api/conversations/{self.conv_classroom.id}/messages/', {
            'body': 'Hello class!'
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['body'], 'Hello class!')

        # 2. Teacher reads message -> 200
        self.client.force_authenticate(user=self.teacher)
        resp = self.client.get(f'/api/conversations/{self.conv_classroom.id}/messages/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data['messages']), 1)

        # 3. Removed member cannot read or post -> 404
        self.client.force_authenticate(user=self.student_removed)
        resp = self.client.get(f'/api/conversations/{self.conv_classroom.id}/messages/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        resp = self.client.post(f'/api/conversations/{self.conv_classroom.id}/messages/', {'body': 'test'})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

        # 4. Outsider cannot read or post -> 404
        self.client.force_authenticate(user=self.student_outsider)
        resp = self.client.get(f'/api/conversations/{self.conv_classroom.id}/messages/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        resp = self.client.post(f'/api/conversations/{self.conv_classroom.id}/messages/', {'body': 'test'})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_group_conversation_authorization(self):
        """Active group members can read/post; removed members and outsiders receive 404."""
        # Active member can post
        self.client.force_authenticate(user=self.student_active)
        resp = self.client.post(f'/api/conversations/{self.conv_group.id}/messages/', {
            'body': 'Lab report notes'
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        # Removed member receives 404
        self.client.force_authenticate(user=self.student_removed)
        resp = self.client.get(f'/api/conversations/{self.conv_group.id}/messages/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

        # Outsider receives 404
        self.client.force_authenticate(user=self.student_outsider)
        resp = self.client.get(f'/api/conversations/{self.conv_group.id}/messages/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_direct_conversation_authorization_and_find_or_create(self):
        """Only DM participants can read/post; outsiders receive 404; find-or-create works."""
        # 1. Participant A posts
        self.client.force_authenticate(user=self.student_active)
        resp = self.client.post(f'/api/conversations/{self.conv_direct.id}/messages/', {
            'body': 'Question about the lab'
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

        # 2. Participant B reads
        self.client.force_authenticate(user=self.teacher)
        resp = self.client.get(f'/api/conversations/{self.conv_direct.id}/messages/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp.data['messages']), 1)

        # 3. Third party receives 404
        self.client.force_authenticate(user=self.student_outsider)
        resp = self.client.get(f'/api/conversations/{self.conv_direct.id}/messages/')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        resp = self.client.post(f'/api/conversations/{self.conv_direct.id}/messages/', {'body': 'eavesdrop'})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

        # 4. Self-DM rejected
        self.client.force_authenticate(user=self.student_active)
        resp = self.client.post('/api/conversations/direct/', {
            'target_user_id': self.student_active.id
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

        # 5. Find-or-create existing DM returns 200 and existing conversation ID
        resp = self.client.post('/api/conversations/direct/', {
            'target_user_id': self.teacher.id
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['id'], self.conv_direct.id)

        # 6. Find-or-create new DM returns 201
        resp = self.client.post('/api/conversations/direct/', {
            'target_user_id': self.student_outsider.id
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertNotEqual(resp.data['id'], self.conv_direct.id)

    def test_conversation_inbox_list(self):
        """GET /api/conversations/ lists only authorized conversations with previews."""
        # Seed a message in direct conversation
        Message.objects.create(
            conversation=self.conv_direct,
            sender=self.teacher,
            body='See you in class tomorrow.'
        )

        self.client.force_authenticate(user=self.student_active)
        resp = self.client.get('/api/conversations/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        conv_ids = [c['id'] for c in resp.data]
        self.assertIn(self.conv_classroom.id, conv_ids)
        self.assertIn(self.conv_group.id, conv_ids)
        self.assertIn(self.conv_direct.id, conv_ids)

        # Check DM metadata
        dm_item = next(c for c in resp.data if c['id'] == self.conv_direct.id)
        self.assertEqual(dm_item['title'], 'auth_teacher')
        self.assertEqual(dm_item['other_user']['username'], 'auth_teacher')
        self.assertEqual(dm_item['last_message']['body'], 'See you in class tomorrow.')

        # Outsider student does not see classroom, group, or direct conversation
        self.client.force_authenticate(user=self.student_outsider)
        resp_outsider = self.client.get('/api/conversations/')
        outsider_conv_ids = [c['id'] for c in resp_outsider.data]
        self.assertNotIn(self.conv_classroom.id, outsider_conv_ids)
        self.assertNotIn(self.conv_group.id, outsider_conv_ids)
        self.assertNotIn(self.conv_direct.id, outsider_conv_ids)

    def test_cursor_pagination(self):
        """Test GET /api/conversations/{id}/messages/?before=...&limit=... pagination."""
        base_time = timezone.now() - timedelta(hours=2)
        messages = []
        for i in range(70):
            # Create messages with staggered timestamps
            msg = Message.objects.create(
                conversation=self.conv_classroom,
                sender=self.student_active,
                body=f"Message {i+1:02d}"
            )
            # Adjust timestamp manually
            msg_time = base_time + timedelta(minutes=i)
            Message.objects.filter(id=msg.id).update(created_at=msg_time)

        self.client.force_authenticate(user=self.student_active)

        # 1. Fetch newest page with limit=25
        resp1 = self.client.get(f'/api/conversations/{self.conv_classroom.id}/messages/?limit=25')
        self.assertEqual(resp1.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp1.data['messages']), 25)
        self.assertTrue(resp1.data['has_more'])
        # Newest page should contain Message 46 to Message 70 in chronological order
        self.assertEqual(resp1.data['messages'][-1]['body'], 'Message 70')
        self.assertEqual(resp1.data['messages'][0]['body'], 'Message 46')

        # 2. Fetch older page using before=oldest_timestamp
        cursor1 = resp1.data['oldest_timestamp']
        resp2 = self.client.get(f'/api/conversations/{self.conv_classroom.id}/messages/?limit=25&before={cursor1}')
        self.assertEqual(resp2.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp2.data['messages']), 25)
        self.assertTrue(resp2.data['has_more'])
        self.assertEqual(resp2.data['messages'][-1]['body'], 'Message 45')
        self.assertEqual(resp2.data['messages'][0]['body'], 'Message 21')

        # 3. Fetch final page
        cursor2 = resp2.data['oldest_timestamp']
        resp3 = self.client.get(f'/api/conversations/{self.conv_classroom.id}/messages/?limit=25&before={cursor2}')
        self.assertEqual(resp3.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resp3.data['messages']), 20)  # Remaining 20 messages (Message 01 to 20)
        self.assertEqual(resp3.data['messages'][-1]['body'], 'Message 20')

    from unittest.mock import patch
    @patch('requests.post')
    def test_broadcast_resilience_on_fastapi_failure(self, mock_post):
        """Test that FastAPI broadcast failures/timeouts do not break message creation in Django."""
        import requests
        # Simulate a connection timeout from FastAPI
        mock_post.side_effect = requests.exceptions.Timeout("Connection timed out")

        self.client.force_authenticate(user=self.student_active)
        resp = self.client.post(f'/api/conversations/{self.conv_classroom.id}/messages/', {
            'body': 'Message sent during FastAPI outage'
        }, format='json')

        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['body'], 'Message sent during FastAPI outage')

        # Verify message persisted to DB despite broadcast timeout
        self.assertTrue(
            Message.objects.filter(
                conversation=self.conv_classroom,
                body='Message sent during FastAPI outage'
            ).exists()
        )

