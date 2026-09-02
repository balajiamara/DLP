from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status

User = get_user_model()


class AuthenticationTestCase(APITestCase):
    def setUp(self):
        self.register_url = reverse('auth_register')
        self.token_url = reverse('token_obtain_pair')
        self.me_url = reverse('auth_me')
        self.search_url = reverse('user_search')

        self.user_data = {
            'email': 'student@example.com',
            'username': 'student1',
            'password': 'StrongPassword123!',
            'role': 'STUDENT'
        }
        self.teacher_data = {
            'email': 'teacher@example.com',
            'username': 'teacher1',
            'password': 'TeacherPassword123!',
            'role': 'TEACHER'
        }

    def test_successful_registration(self):
        """Test successful registration with valid data."""
        response = self.client.post(self.register_url, self.user_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.count(), 1)

        user = User.objects.get(email=self.user_data['email'])
        self.assertEqual(user.username, self.user_data['username'])
        self.assertEqual(user.role, 'STUDENT')
        self.assertTrue(user.check_password(self.user_data['password']))

    def test_registration_fails_duplicate_email(self):
        """Test registration fails when email is already registered."""
        self.client.post(self.register_url, self.user_data, format='json')

        duplicate_email_data = self.user_data.copy()
        duplicate_email_data['username'] = 'student2'
        response = self.client.post(self.register_url, duplicate_email_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)

    def test_registration_fails_invalid_role(self):
        """Test registration fails when role is invalid."""
        invalid_role_data = self.user_data.copy()
        invalid_role_data['role'] = 'INVALID_ROLE'
        response = self.client.post(self.register_url, invalid_role_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('role', response.data)

    def test_login_correct_credentials_returns_tokens(self):
        """Test login with correct email and password returns JWT access & refresh tokens."""
        self.client.post(self.register_url, self.user_data, format='json')

        login_data = {
            'email': self.user_data['email'],
            'password': self.user_data['password']
        }
        response = self.client.post(self.token_url, login_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_login_wrong_password_fails(self):
        """Test login with incorrect password returns 401 Unauthorized."""
        self.client.post(self.register_url, self.user_data, format='json')

        login_data = {
            'email': self.user_data['email'],
            'password': 'WrongPassword123!'
        }
        response = self.client.post(self.token_url, login_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_endpoint_returns_user_when_authenticated(self):
        """Test GET /api/auth/me/ returns current user profile when authenticated."""
        self.client.post(self.register_url, self.user_data, format='json')

        login_data = {
            'email': self.user_data['email'],
            'password': self.user_data['password']
        }
        token_response = self.client.post(self.token_url, login_data, format='json')
        access_token = token_response.data['access']

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        me_response = self.client.get(self.me_url)

        self.assertEqual(me_response.status_code, status.HTTP_200_OK)
        self.assertEqual(me_response.data['email'], self.user_data['email'])
        self.assertEqual(me_response.data['username'], self.user_data['username'])
        self.assertEqual(me_response.data['role'], self.user_data['role'])

    def test_me_endpoint_returns_401_when_unauthenticated(self):
        """Test GET /api/auth/me/ returns 401 Unauthorized when no credentials provided."""
        response = self.client.get(self.me_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_successfully_updating_own_profile(self):
        """Test PATCH /api/auth/me/ successfully updates username, first_name, and last_name."""
        self.client.post(self.register_url, self.user_data, format='json')
        user = User.objects.get(email=self.user_data['email'])
        self.client.force_authenticate(user=user)

        patch_data = {
            'username': 'new_student_username',
            'first_name': 'John',
            'last_name': 'Doe'
        }
        response = self.client.patch(self.me_url, patch_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'new_student_username')
        self.assertEqual(response.data['first_name'], 'John')
        self.assertEqual(response.data['last_name'], 'Doe')

        user.refresh_from_db()
        self.assertEqual(user.username, 'new_student_username')

    def test_update_fails_if_username_already_taken(self):
        """Test PATCH /api/auth/me/ fails if new username is already taken by another user."""
        self.client.post(self.register_url, self.user_data, format='json')
        self.client.post(self.register_url, self.teacher_data, format='json')

        user = User.objects.get(email=self.user_data['email'])
        self.client.force_authenticate(user=user)

        patch_data = {'username': self.teacher_data['username']}
        response = self.client.patch(self.me_url, patch_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('username', response.data)

    def test_cannot_change_email_or_role_via_profile_update(self):
        """Test PATCH /api/auth/me/ ignores/rejects attempts to change email or role."""
        self.client.post(self.register_url, self.user_data, format='json')
        user = User.objects.get(email=self.user_data['email'])
        self.client.force_authenticate(user=user)

        patch_data = {
            'email': 'hacked_email@example.com',
            'role': 'TEACHER',
            'username': 'updated_username'
        }
        response = self.client.patch(self.me_url, patch_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        user.refresh_from_db()
        self.assertEqual(user.email, self.user_data['email'])
        self.assertEqual(user.role, 'STUDENT')
        self.assertEqual(user.username, 'updated_username')

    def test_user_search_returns_matching_users_by_partial_username(self):
        """Test GET /api/users/search/?q=<query> returns matching users by partial username."""
        self.client.post(self.register_url, self.user_data, format='json')
        self.client.post(self.register_url, self.teacher_data, format='json')

        user = User.objects.get(email=self.user_data['email'])
        self.client.force_authenticate(user=user)

        search_url = self.search_url + '?q=teacher'
        response = self.client.get(search_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['username'], 'teacher1')
        self.assertEqual(results[0]['role'], 'TEACHER')

    def test_user_search_does_not_expose_email_addresses(self):
        """Test GET /api/users/search/?q=<query> does not expose private fields like email."""
        self.client.post(self.register_url, self.user_data, format='json')
        user = User.objects.get(email=self.user_data['email'])
        self.client.force_authenticate(user=user)

        search_url = self.search_url + '?q=student'
        response = self.client.get(search_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['results']
        self.assertTrue(len(results) > 0)
        self.assertNotIn('email', results[0])
        self.assertNotIn('password', results[0])
        self.assertIn('id', results[0])
        self.assertIn('username', results[0])
        self.assertIn('role', results[0])

    def test_user_search_requires_authentication(self):
        """Test GET /api/users/search/ returns 401 when unauthenticated."""
        search_url = self.search_url + '?q=student'
        response = self.client.get(search_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
