from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status

from .models import Group, GroupMembership

User = get_user_model()


class GroupTestCase(APITestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            email='student1@example.com',
            username='student1',
            password='Password123!',
            role='STUDENT'
        )
        self.user2 = User.objects.create_user(
            email='student2@example.com',
            username='student2',
            password='Password123!',
            role='STUDENT'
        )
        self.teacher1 = User.objects.create_user(
            email='teacher1@example.com',
            username='teacher1',
            password='Password123!',
            role='TEACHER'
        )

        self.list_create_url = reverse('group_list_create')

    def test_user_can_create_group_and_becomes_first_member(self):
        """Test any authenticated user can create a group and becomes its first ACTIVE member."""
        self.client.force_authenticate(user=self.user1)
        payload = {
            'name': 'Python Algorithms Study Group',
            'description': 'Daily LeetCode & Python practice'
        }
        response = self.client.post(self.list_create_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Group.objects.count(), 1)

        group = Group.objects.get(pk=response.data['id'])
        self.assertEqual(group.created_by, self.user1)
        self.assertEqual(group.name, 'Python Algorithms Study Group')

        # Check membership
        self.assertEqual(group.memberships.count(), 1)
        membership = group.memberships.first()
        self.assertEqual(membership.user, self.user1)
        self.assertEqual(membership.status, GroupMembership.MembershipStatus.ACTIVE)

    def test_member_can_add_another_user_to_group(self):
        """Test an active member can add another user to the group via username or user_id."""
        group = Group.objects.create(name='Django Devs', created_by=self.user1)
        GroupMembership.objects.create(user=self.user1, group=group, status='ACTIVE')

        add_member_url = reverse('add_group_member', kwargs={'pk': group.id})
        self.client.force_authenticate(user=self.user1)

        payload = {'username': self.user2.username}
        response = self.client.post(add_member_url, payload, format='json')

        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])
        self.assertTrue(GroupMembership.objects.filter(
            user=self.user2, group=group, status='ACTIVE'
        ).exists())

    def test_cannot_add_user_who_is_already_active_member(self):
        """Test adding an already active member returns 200 OK without creating duplicate or error."""
        group = Group.objects.create(name='Django Devs', created_by=self.user1)
        GroupMembership.objects.create(user=self.user1, group=group, status='ACTIVE')
        GroupMembership.objects.create(user=self.user2, group=group, status='ACTIVE')

        add_member_url = reverse('add_group_member', kwargs={'pk': group.id})
        self.client.force_authenticate(user=self.user1)

        payload = {'user_id': self.user2.id}
        response = self.client.post(add_member_url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('detail', response.data)
        self.assertEqual(GroupMembership.objects.filter(user=self.user2, group=group).count(), 1)

    def test_non_member_gets_404_on_group_detail(self):
        """Test a non-member gets 404 Not Found on group detail endpoint."""
        group = Group.objects.create(name='Private Group', created_by=self.user1)
        GroupMembership.objects.create(user=self.user1, group=group, status='ACTIVE')

        detail_url = reverse('group_detail', kwargs={'pk': group.id})

        # User 2 (non-member) requests detail
        self.client.force_authenticate(user=self.user2)
        response = self.client.get(detail_url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_member_can_leave_group_and_is_removed_from_active_list(self):
        """Test a member can leave a group, and soft-removed member no longer appears in GET /api/groups/."""
        group = Group.objects.create(name='Study Group', created_by=self.user1)
        GroupMembership.objects.create(user=self.user1, group=group, status='ACTIVE')

        leave_url = reverse('leave_group', kwargs={'pk': group.id})

        # User 1 leaves group
        self.client.force_authenticate(user=self.user1)
        leave_response = self.client.post(leave_url)
        self.assertEqual(leave_response.status_code, status.HTTP_200_OK)

        # Check membership status updated to REMOVED
        membership = GroupMembership.objects.get(user=self.user1, group=group)
        self.assertEqual(membership.status, GroupMembership.MembershipStatus.REMOVED)

        # Check user no longer sees group in list endpoint
        list_response = self.client.get(self.list_create_url)
        results = list_response.data if isinstance(list_response.data, list) else list_response.data.get('results')
        self.assertEqual(len(results), 0)
