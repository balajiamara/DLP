import json
from unittest.mock import patch, AsyncMock, MagicMock
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status

from classrooms.models import Classroom, ClassroomMembership

User = get_user_model()


class ChatStreamProxyTests(APITestCase):
    def setUp(self):
        # Create teacher
        self.teacher = User.objects.create_user(
            username="teacher_chat",
            email="teacher_chat@example.com",
            password="Password123!",
            role="TEACHER",
        )

        # Create student
        self.student = User.objects.create_user(
            username="student_chat",
            email="student_chat@example.com",
            password="Password123!",
            role="STUDENT",
        )

        # Create outsider
        self.outsider = User.objects.create_user(
            username="outsider_chat",
            email="outsider_chat@example.com",
            password="Password123!",
            role="STUDENT",
        )

        # Create classroom
        self.classroom = Classroom.objects.create(
            name="Physics 101",
            description="Physics intro",
            teacher=self.teacher,
        )

        # Enroll student
        ClassroomMembership.objects.create(
            user=self.student,
            classroom=self.classroom,
            role_in_classroom=ClassroomMembership.RoleInClassroom.STUDENT,
            status=ClassroomMembership.MembershipStatus.ACTIVE,
        )

    # -------------------------------------------------------------
    # COURSE CHAT STREAM TESTS
    # -------------------------------------------------------------

    def test_course_stream_unauthenticated(self):
        """Unauthenticated requests must receive 401 Unauthorized."""
        res = self.client.post("/api/chat/course/stream", {"classroom_id": self.classroom.id, "query": "Hi"})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_course_stream_missing_fields(self):
        """Missing classroom_id or query must receive 400 Bad Request."""
        self.client.force_authenticate(user=self.student)
        res = self.client.post("/api/chat/course/stream", {"classroom_id": self.classroom.id})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_course_stream_forbidden_for_outsider(self):
        """User who is not in the classroom must receive 403 Forbidden before streaming."""
        self.client.force_authenticate(user=self.outsider)
        res = self.client.post(
            "/api/chat/course/stream",
            {"classroom_id": self.classroom.id, "query": "What is force?"},
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("Access denied", res.data["detail"])

    @patch("chat.views.httpx.AsyncClient")
    def test_course_stream_success_for_member(self, mock_client_cls):
        """Active student receives 200 StreamingHttpResponse with text/event-stream."""
        self.client.force_authenticate(user=self.student)

        # Mock httpx.AsyncClient stream
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.aclose = AsyncMock()

        mock_resp = MagicMock()
        mock_resp.status_code = 200

        async def fake_aiter_lines():
            yield 'data: {"type": "chunk", "delta": "Force is"}'
            yield 'data: {"type": "chunk", "delta": " mass times acceleration."}'
            yield 'data: {"type": "done", "grounded": true, "sources": []}'

        mock_resp.aiter_lines = fake_aiter_lines

        # context manager for client.stream
        mock_stream_ctx = MagicMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_client.stream.return_value = mock_stream_ctx

        res = self.client.post(
            "/api/chat/course/stream",
            {"classroom_id": self.classroom.id, "query": "What is force?"},
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("text/event-stream", res["Content-Type"])

    # -------------------------------------------------------------
    # GENERAL CHAT STREAM TESTS
    # -------------------------------------------------------------

    def test_general_stream_unauthenticated(self):
        """Unauthenticated requests must receive 401 Unauthorized."""
        res = self.client.post("/api/chat/general/stream", {"classroom_id": self.classroom.id, "query": "Hi"})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_general_stream_missing_fields(self):
        """Missing classroom_id or query must receive 400 Bad Request."""
        self.client.force_authenticate(user=self.student)
        res = self.client.post("/api/chat/general/stream", {"query": "Hello"})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_general_stream_forbidden_for_outsider(self):
        """User who is not in the classroom must receive 403 Forbidden before streaming."""
        self.client.force_authenticate(user=self.outsider)
        res = self.client.post(
            "/api/chat/general/stream",
            {"classroom_id": self.classroom.id, "query": "Tell me a joke"},
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("Access denied", res.data["detail"])

    @patch("chat.views.httpx.AsyncClient")
    def test_general_stream_success_for_member(self, mock_client_cls):
        """Active student receives 200 StreamingHttpResponse with text/event-stream."""
        self.client.force_authenticate(user=self.student)

        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.aclose = AsyncMock()

        mock_resp = MagicMock()
        mock_resp.status_code = 200

        async def fake_aiter_lines():
            yield 'data: {"type": "chunk", "delta": "General"}'
            yield 'data: {"type": "chunk", "delta": " response"}'
            yield 'data: {"type": "done", "grounded": false, "sources": []}'

        mock_resp.aiter_lines = fake_aiter_lines

        mock_stream_ctx = MagicMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)
        mock_client.stream.return_value = mock_stream_ctx

        res = self.client.post(
            "/api/chat/general/stream",
            {"classroom_id": self.classroom.id, "query": "Tell me a joke"},
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("text/event-stream", res["Content-Type"])

    # -------------------------------------------------------------
    # FEEDBACK PROXY TESTS
    # -------------------------------------------------------------

    def test_feedback_unauthenticated(self):
        """Unauthenticated feedback requests must receive 401 Unauthorized."""
        res = self.client.post("/api/chat/feedback", {"log_id": "11111111-1111-1111-1111-111111111111", "rating": "up"})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_feedback_missing_fields(self):
        """Missing log_id or rating must receive 400 Bad Request."""
        self.client.force_authenticate(user=self.student)
        res = self.client.post("/api/chat/feedback", {"rating": "up"})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_feedback_invalid_rating(self):
        """Rating not 'up' or 'down' must receive 400 Bad Request."""
        self.client.force_authenticate(user=self.student)
        res = self.client.post(
            "/api/chat/feedback",
            {"log_id": "11111111-1111-1111-1111-111111111111", "rating": "invalid"},
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("chat.views.httpx.Client")
    def test_feedback_success(self, mock_client_cls):
        """Authenticated student successfully submits feedback and gets 200 response."""
        self.client.force_authenticate(user=self.student)

        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.json.return_value = {
            "status": "recorded",
            "log_id": "11111111-1111-1111-1111-111111111111",
            "rating": "up",
        }
        mock_client.post.return_value = mock_resp

        res = self.client.post(
            "/api/chat/feedback",
            {
                "log_id": "11111111-1111-1111-1111-111111111111",
                "rating": "up",
                "reason": "Very helpful explanation!",
            },
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["status"], "recorded")
        self.assertEqual(res.data["rating"], "up")

