from unittest.mock import patch, MagicMock
from django.contrib.auth import get_user_model
from django.conf import settings
from rest_framework.test import APITestCase
from rest_framework import status

from classrooms.models import Classroom, ClassroomMembership
from syllabus.models import Course, Module, Topic
from .models import Assignment, Quiz, Question, GeneratedDraft

User = get_user_model()


class DraftLifecycleAPITests(APITestCase):
    def setUp(self):
        # Teacher 1 (Classroom 1 Owner)
        self.teacher1 = User.objects.create_user(
            email='teacher1@example.com',
            username='teacher1',
            password='Password123!',
            role='TEACHER'
        )
        self.classroom1 = Classroom.objects.create(
            name='Physics 101',
            description='Classical Mechanics',
            teacher=self.teacher1
        )
        ClassroomMembership.objects.create(
            user=self.teacher1,
            classroom=self.classroom1,
            role_in_classroom='TEACHER',
            status=ClassroomMembership.MembershipStatus.ACTIVE
        )

        # Student 1 (Member of Classroom 1)
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

        # Student 2 (Member of Classroom 1)
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

        # Outsider user (Not a member)
        self.outsider = User.objects.create_user(
            email='outsider@example.com',
            username='outsider',
            password='Password123!',
            role='STUDENT'
        )

        # Course hierarchy
        self.course = Course.objects.create(classroom=self.classroom1, title='Mechanics')
        self.module = Module.objects.create(course=self.course, title='Kinematics', order=1)
        self.topic = Topic.objects.create(module=self.module, title='Vectors and Motion', order=1)

    def test_internal_draft_create_missing_secret(self):
        """Internal draft endpoint rejects requests missing X-Internal-Secret."""
        payload = {
            "classroom": self.classroom1.id,
            "content_type": "QUIZ",
            "content": {"title": "Test", "questions": []},
            "created_by": self.teacher1.id,
        }
        res = self.client.post('/api/internal/drafts/', data=payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_internal_draft_create_success(self):
        """Internal draft endpoint creates a draft when presented with valid internal secret."""
        payload = {
            "classroom": self.classroom1.id,
            "content_type": "QUIZ",
            "status": "DRAFT",
            "content": {
                "title": "Vectors Quiz",
                "questions": [
                    {
                        "question": "What is a vector?",
                        "option_a": "Magnitude only",
                        "option_b": "Magnitude and direction",
                        "option_c": "Direction only",
                        "option_d": "None of the above",
                        "correct_option": "B",
                        "explanation": "A vector quantity has both magnitude and direction."
                    }
                ]
            },
            "topic": self.topic.id,
            "created_by": self.teacher1.id,
            "requires_teacher_fact_check": True,
        }
        res = self.client.post(
            '/api/internal/drafts/',
            data=payload,
            format='json',
            HTTP_X_INTERNAL_SECRET=settings.INTERNAL_SERVICE_SECRET
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        draft = GeneratedDraft.objects.get(id=res.data['id'])
        self.assertEqual(draft.status, GeneratedDraft.Status.DRAFT)
        self.assertEqual(draft.content_type, GeneratedDraft.ContentType.QUIZ)
        self.assertTrue(draft.requires_teacher_fact_check)
        self.assertIn("Schema validation confirms structure and format only", res.data['review_notice'])

    def test_draft_list_teacher_vs_student_visibility(self):
        """Teachers can see all classroom drafts; students only see their targeted study plans."""
        # Draft 1: Quiz draft
        quiz_draft = GeneratedDraft.objects.create(
            classroom=self.classroom1,
            content_type=GeneratedDraft.ContentType.QUIZ,
            status=GeneratedDraft.Status.DRAFT,
            content={"title": "Quiz 1", "questions": []},
            created_by=self.teacher1,
        )
        # Draft 2: Study plan for student 1
        plan_draft1 = GeneratedDraft.objects.create(
            classroom=self.classroom1,
            content_type=GeneratedDraft.ContentType.STUDY_PLAN,
            status=GeneratedDraft.Status.DRAFT,
            content={"title": "Plan for Student 1", "tasks": []},
            created_by=self.teacher1,
            target_student=self.student1,
        )
        # Draft 3: Study plan for student 2
        plan_draft2 = GeneratedDraft.objects.create(
            classroom=self.classroom1,
            content_type=GeneratedDraft.ContentType.STUDY_PLAN,
            status=GeneratedDraft.Status.DRAFT,
            content={"title": "Plan for Student 2", "tasks": []},
            created_by=self.teacher1,
            target_student=self.student2,
        )

        # Teacher should see all 3 drafts
        self.client.force_authenticate(user=self.teacher1)
        res = self.client.get(f'/api/classrooms/{self.classroom1.id}/drafts/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 3)

        # Student 1 should only see draft 2 (their targeted study plan)
        self.client.force_authenticate(user=self.student1)
        res = self.client.get(f'/api/classrooms/{self.classroom1.id}/drafts/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]['id'], plan_draft1.id)

        # Outsider user gets 404
        self.client.force_authenticate(user=self.outsider)
        res = self.client.get(f'/api/classrooms/{self.classroom1.id}/drafts/')
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_approve_quiz_draft_creates_real_quiz_and_questions_with_explanation(self):
        """Approving a quiz draft creates real Quiz and Question records and preserves explanation."""
        draft = GeneratedDraft.objects.create(
            classroom=self.classroom1,
            content_type=GeneratedDraft.ContentType.QUIZ,
            status=GeneratedDraft.Status.DRAFT,
            content={
                "title": "Kinematics Assessment",
                "questions": [
                    {
                        "question": "What is acceleration?",
                        "option_a": "Change in displacement",
                        "option_b": "Rate of change of velocity",
                        "option_c": "Force times distance",
                        "option_d": "Mass times gravity",
                        "correct_option": "B",
                        "explanation": "Acceleration is the derivative of velocity with respect to time."
                    }
                ]
            },
            topic=self.topic,
            created_by=self.teacher1,
        )

        self.client.force_authenticate(user=self.teacher1)
        res = self.client.post(f'/api/classrooms/{self.classroom1.id}/drafts/{draft.id}/approve/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        draft.refresh_from_db()
        self.assertEqual(draft.status, GeneratedDraft.Status.APPROVED)
        self.assertIsNotNone(draft.approved_quiz)

        # Verify real Quiz and Question records exist in the database
        quiz = draft.approved_quiz
        self.assertEqual(quiz.title, "Kinematics Assessment")
        self.assertEqual(quiz.classroom, self.classroom1)
        self.assertEqual(quiz.topic, self.topic)
        self.assertEqual(quiz.questions.count(), 1)

        question = quiz.questions.first()
        self.assertEqual(question.text, "What is acceleration?")
        self.assertEqual(question.correct_option, "B")
        self.assertEqual(question.explanation, "Acceleration is the derivative of velocity with respect to time.")

    def test_approve_study_plan_draft_creates_real_assignment(self):
        """Approving a study plan draft creates a real Assignment record."""
        draft = GeneratedDraft.objects.create(
            classroom=self.classroom1,
            content_type=GeneratedDraft.ContentType.STUDY_PLAN,
            status=GeneratedDraft.Status.DRAFT,
            content={
                "title": "Kinematics Recovery Plan",
                "overview": "Spend 3 days mastering vector addition.",
                "tasks": [
                    {
                        "title": "Practice Vector Addition",
                        "description": "Solve problems 1-5 in module notes.",
                        "target_topic_name": "Vectors and Motion",
                        "suggested_pacing": "Day 1 (45 mins)",
                        "suggested_due_date": "2026-09-18"
                    }
                ]
            },
            topic=self.topic,
            created_by=self.teacher1,
            target_student=self.student1,
        )

        self.client.force_authenticate(user=self.teacher1)
        res = self.client.post(f'/api/classrooms/{self.classroom1.id}/drafts/{draft.id}/approve/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        draft.refresh_from_db()
        self.assertEqual(draft.status, GeneratedDraft.Status.APPROVED)
        self.assertIsNotNone(draft.approved_assignment)

        assignment = draft.approved_assignment
        self.assertEqual(assignment.title, "Kinematics Recovery Plan")
        self.assertIn("Practice Vector Addition", assignment.description)
        self.assertIn("Spend 3 days mastering vector addition", assignment.description)

    def test_reject_draft_marks_rejected_and_creates_no_records(self):
        """Rejecting a draft marks it REJECTED and creates no live records."""
        draft = GeneratedDraft.objects.create(
            classroom=self.classroom1,
            content_type=GeneratedDraft.ContentType.QUIZ,
            status=GeneratedDraft.Status.DRAFT,
            content={"title": "Poor Quality Quiz", "questions": []},
            created_by=self.teacher1,
        )

        self.client.force_authenticate(user=self.teacher1)
        res = self.client.post(f'/api/classrooms/{self.classroom1.id}/drafts/{draft.id}/reject/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        draft.refresh_from_db()
        self.assertEqual(draft.status, GeneratedDraft.Status.REJECTED)
        self.assertIsNone(draft.approved_quiz)
        self.assertEqual(Quiz.objects.count(), 0)

    def test_cannot_re_approve_or_re_reject_draft(self):
        """A draft that is already APPROVED or REJECTED cannot be approved or rejected again."""
        draft = GeneratedDraft.objects.create(
            classroom=self.classroom1,
            content_type=GeneratedDraft.ContentType.QUIZ,
            status=GeneratedDraft.Status.APPROVED,
            content={"title": "Already Done", "questions": []},
            created_by=self.teacher1,
        )

        self.client.force_authenticate(user=self.teacher1)
        res = self.client.post(f'/api/classrooms/{self.classroom1.id}/drafts/{draft.id}/approve/')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        res_reject = self.client.post(f'/api/classrooms/{self.classroom1.id}/drafts/{draft.id}/reject/')
        self.assertEqual(res_reject.status_code, status.HTTP_400_BAD_REQUEST)

    def test_generate_quiz_unauthenticated(self):
        """Unauthenticated calls to generate-quiz proxy are rejected with 401."""
        res = self.client.post(f'/api/classrooms/{self.classroom1.id}/drafts/generate-quiz/', data={"topic_id": self.topic.id})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_generate_quiz_student_forbidden(self):
        """Students cannot trigger quiz generation (teacher-only action -> 403)."""
        self.client.force_authenticate(user=self.student1)
        res = self.client.post(f'/api/classrooms/{self.classroom1.id}/drafts/generate-quiz/', data={"topic_id": self.topic.id})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_generate_quiz_missing_topic_id(self):
        """Quiz generation requires topic_id -> 400."""
        self.client.force_authenticate(user=self.teacher1)
        res = self.client.post(f'/api/classrooms/{self.classroom1.id}/drafts/generate-quiz/', data={})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('httpx.Client.post')
    def test_generate_quiz_proxy_success(self, mock_post):
        """Teacher can trigger quiz generation; proxy forwards to FastAPI with X-Internal-Secret."""
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.json.return_value = {
            "id": 99,
            "classroom": self.classroom1.id,
            "content_type": "QUIZ",
            "status": "DRAFT",
            "content": {"title": "Grounded Motion Quiz", "questions": []},
            "requires_teacher_fact_check": True,
        }
        mock_post.return_value = mock_resp

        self.client.force_authenticate(user=self.teacher1)
        res = self.client.post(
            f'/api/classrooms/{self.classroom1.id}/drafts/generate-quiz/',
            data={"topic_id": self.topic.id, "num_questions": 3},
            format='json'
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["id"], 99)
        self.assertTrue(res.data["requires_teacher_fact_check"])

        # Confirm proxy forwarded secret and correct payload
        mock_post.assert_called_once()
        call_args, call_kwargs = mock_post.call_args
        self.assertIn("/content/generate-quiz", call_args[0])
        self.assertEqual(call_kwargs["headers"]["X-Internal-Secret"], settings.INTERNAL_SERVICE_SECRET)
        self.assertEqual(call_kwargs["json"]["classroom_id"], self.classroom1.id)
        self.assertEqual(call_kwargs["json"]["topic_id"], self.topic.id)
        self.assertEqual(call_kwargs["json"]["teacher_user_id"], self.teacher1.id)
        self.assertEqual(call_kwargs["json"]["num_questions"], 3)

    def test_generate_study_plan_unauthenticated(self):
        """Unauthenticated calls to generate-study-plan proxy return 401."""
        res = self.client.post(f'/api/classrooms/{self.classroom1.id}/drafts/generate-study-plan/', data={"goal_description": "Learn physics"})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_generate_study_plan_outsider_not_found(self):
        """Non-members cannot generate study plans -> 404."""
        self.client.force_authenticate(user=self.outsider)
        res = self.client.post(f'/api/classrooms/{self.classroom1.id}/drafts/generate-study-plan/', data={"goal_description": "Learn physics"})
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_generate_study_plan_missing_goal(self):
        """Study plan generation requires goal_description -> 400."""
        self.client.force_authenticate(user=self.student1)
        res = self.client.post(f'/api/classrooms/{self.classroom1.id}/drafts/generate-study-plan/', data={})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_generate_study_plan_teacher_requires_student(self):
        """Teacher generating study plan must specify student_user_id -> 400."""
        self.client.force_authenticate(user=self.teacher1)
        res = self.client.post(
            f'/api/classrooms/{self.classroom1.id}/drafts/generate-study-plan/',
            data={"goal_description": "Remediation plan"},
            format='json'
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('httpx.Client.post')
    def test_generate_study_plan_student_self_service_success(self, mock_post):
        """Student can trigger self-service study plan generation."""
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.headers = {"content-type": "application/json"}
        mock_resp.json.return_value = {
            "id": 100,
            "classroom": self.classroom1.id,
            "content_type": "STUDY_PLAN",
            "status": "DRAFT",
            "content": {"title": "Student 1 Study Plan", "tasks": []},
            "requires_teacher_fact_check": True,
        }
        mock_post.return_value = mock_resp

        self.client.force_authenticate(user=self.student1)
        res = self.client.post(
            f'/api/classrooms/{self.classroom1.id}/drafts/generate-study-plan/',
            data={"goal_description": "Master kinematics vectors", "deadline": "2026-09-30"},
            format='json'
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["id"], 100)

        # Confirm proxy forwarded student1 as both requester and target
        mock_post.assert_called_once()
        call_args, call_kwargs = mock_post.call_args
        self.assertIn("/content/generate-study-plan", call_args[0])
        self.assertEqual(call_kwargs["headers"]["X-Internal-Secret"], settings.INTERNAL_SERVICE_SECRET)
        self.assertEqual(call_kwargs["json"]["classroom_id"], self.classroom1.id)
        self.assertEqual(call_kwargs["json"]["student_user_id"], self.student1.id)
        self.assertEqual(call_kwargs["json"]["requesting_user_id"], self.student1.id)
        self.assertEqual(call_kwargs["json"]["goal_description"], "Master kinematics vectors")

