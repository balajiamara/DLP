from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status
from classrooms.models import Classroom, ClassroomMembership
from syllabus.models import Course, Module, Topic, TopicProgress
from .models import Assignment, Submission, Quiz, Question, QuizAttempt

User = get_user_model()


class AssessmentsAPITests(APITestCase):
    def setUp(self):
        # Teacher 1 (Owner of Classroom 1)
        self.teacher1 = User.objects.create_user(
            email='teacher1@example.com',
            username='teacher1',
            password='Password123!',
            role='TEACHER'
        )
        self.classroom1 = Classroom.objects.create(
            name='Calculus I',
            description='Limits and Derivatives',
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
        self.course = Course.objects.create(classroom=self.classroom1, title='Math Course', order=1)
        self.module = Module.objects.create(course=self.course, title='Derivatives Module', order=1)
        self.topic = Topic.objects.create(module=self.module, title='Chain Rule', order=1)

    def test_teacher_can_create_assignment_and_quiz_with_nested_questions(self):
        """Teacher can create an assignment and a quiz with nested questions."""
        self.client.force_authenticate(user=self.teacher1)
        base_url = f'/api/classrooms/{self.classroom1.id}'

        # 1. Create Assignment
        assignment_res = self.client.post(f'{base_url}/assignments/', {
            'title': 'Homework 1: Chain Rule',
            'description': 'Solve problems 1-10',
            'topic': self.topic.id
        })
        self.assertEqual(assignment_res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(assignment_res.data['title'], 'Homework 1: Chain Rule')

        # 2. Create Quiz with nested questions
        quiz_res = self.client.post(f'{base_url}/quizzes/', {
            'title': 'Pop Quiz: Derivatives',
            'topic': self.topic.id,
            'questions': [
                {
                    'text': 'What is derivative of x^2?',
                    'option_a': 'x', 'option_b': '2x', 'option_c': 'x^2', 'option_d': '2',
                    'correct_option': 'B', 'order': 1
                },
                {
                    'text': 'What is derivative of sin(x)?',
                    'option_a': 'cos(x)', 'option_b': '-cos(x)', 'option_c': 'sin(x)', 'option_d': '-sin(x)',
                    'correct_option': 'A', 'order': 2
                }
            ]
        }, format='json')
        self.assertEqual(quiz_res.status_code, status.HTTP_201_CREATED)
        quiz_id = quiz_res.data['id']
        self.assertEqual(len(quiz_res.data['questions']), 2)
        self.assertEqual(Question.objects.filter(quiz_id=quiz_id).count(), 2)

    def test_student_submit_and_resubmit_updates_record(self):
        """Student submits assignment; re-submitting updates the submission rather than creating duplicates."""
        assignment = Assignment.objects.create(
            classroom=self.classroom1,
            title='Essay 1',
            created_by=self.teacher1
        )
        submit_url = f'/api/classrooms/{self.classroom1.id}/assignments/{assignment.id}/submit/'

        self.client.force_authenticate(user=self.student1)

        # 1. Initial Submission
        res1 = self.client.post(submit_url, {'content': 'Initial draft of essay.'})
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Submission.objects.filter(assignment=assignment, student=self.student1).count(), 1)

        # 2. Re-submission
        res2 = self.client.post(submit_url, {'content': 'Final revised essay.'})
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertEqual(Submission.objects.filter(assignment=assignment, student=self.student1).count(), 1)

        submission = Submission.objects.get(assignment=assignment, student=self.student1)
        self.assertEqual(submission.content, 'Final revised essay.')

    def test_submission_view_permissions_and_teacher_grading(self):
        """Teacher can view all submissions and grade them; students only view their own."""
        assignment = Assignment.objects.create(
            classroom=self.classroom1,
            title='Project Report',
            created_by=self.teacher1
        )
        sub1 = Submission.objects.create(assignment=assignment, student=self.student1, content='Report 1')
        sub2 = Submission.objects.create(assignment=assignment, student=self.student2, content='Report 2')

        base_url = f'/api/classrooms/{self.classroom1.id}/assignments/{assignment.id}'

        # 1. Student 1 views own submission
        self.client.force_authenticate(user=self.student1)
        my_sub_res = self.client.get(f'{base_url}/my-submission/')
        self.assertEqual(my_sub_res.status_code, status.HTTP_200_OK)
        self.assertEqual(my_sub_res.data['content'], 'Report 1')

        # 2. Student 1 attempts teacher-only list endpoint -> 403 Forbidden
        all_subs_res = self.client.get(f'{base_url}/submissions/')
        self.assertEqual(all_subs_res.status_code, status.HTTP_403_FORBIDDEN)

        # 3. Teacher views all submissions -> 200 OK
        self.client.force_authenticate(user=self.teacher1)
        teacher_list_res = self.client.get(f'{base_url}/submissions/')
        self.assertEqual(teacher_list_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(teacher_list_res.data), 2)

        # 4. Teacher grades student 1's submission
        feedback_url = f'/api/classrooms/{self.classroom1.id}/submissions/{sub1.id}/feedback/'
        grade_res = self.client.patch(feedback_url, {'feedback': 'Excellent analysis!', 'grade': 'A+'})
        self.assertEqual(grade_res.status_code, status.HTTP_200_OK)
        self.assertEqual(grade_res.data['grade'], 'A+')

        sub1.refresh_from_db()
        self.assertEqual(sub1.feedback, 'Excellent analysis!')

    def test_quiz_conceals_correct_option_before_attempt(self):
        """Quiz detail/list conceals correct_option from students who haven't attempted it yet."""
        quiz = Quiz.objects.create(classroom=self.classroom1, title='Secret Quiz', created_by=self.teacher1)
        q1 = Question.objects.create(quiz=quiz, text='Q1', option_a='A', option_b='B', option_c='C', option_d='D', correct_option='A', order=1)

        detail_url = f'/api/classrooms/{self.classroom1.id}/quizzes/{quiz.id}/'

        # Student views quiz detail before attempt
        self.client.force_authenticate(user=self.student1)
        res = self.client.get(detail_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        questions = res.data['questions']
        self.assertNotIn('correct_option', questions[0])

        # Teacher views quiz detail -> correct_option IS visible
        self.client.force_authenticate(user=self.teacher1)
        teacher_res = self.client.get(detail_url)
        self.assertEqual(teacher_res.status_code, status.HTTP_200_OK)
        self.assertIn('correct_option', teacher_res.data['questions'][0])

    def test_server_side_scoring_and_single_attempt_limit(self):
        """Quiz attempt score is calculated server-side; retakes are rejected with 400 Bad Request."""
        quiz = Quiz.objects.create(classroom=self.classroom1, title='Graded Quiz', created_by=self.teacher1)
        q1 = Question.objects.create(quiz=quiz, text='Q1', option_a='A', option_b='B', option_c='C', option_d='D', correct_option='A', order=1)
        q2 = Question.objects.create(quiz=quiz, text='Q2', option_a='A', option_b='B', option_c='C', option_d='D', correct_option='B', order=2)
        q3 = Question.objects.create(quiz=quiz, text='Q3', option_a='A', option_b='B', option_c='C', option_d='D', correct_option='C', order=3)

        attempt_url = f'/api/classrooms/{self.classroom1.id}/quizzes/{quiz.id}/attempt/'
        self.client.force_authenticate(user=self.student1)

        # 1. First Attempt with 2 right (Q1=A, Q2=B) and 1 wrong (Q3=D) -> 2/3 = 67%
        res1 = self.client.post(attempt_url, {
            'answers': {str(q1.id): 'A', str(q2.id): 'B', str(q3.id): 'D'}
        }, format='json')
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res1.data['score'], 67)

        # 2. Second Attempt attempt -> 400 Bad Request
        res2 = self.client.post(attempt_url, {
            'answers': {str(q1.id): 'A', str(q2.id): 'A', str(q3.id): 'A'}
        }, format='json')
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already attempted', res2.data['detail'])

    def test_quiz_attempt_updates_topic_progress_without_downgrade(self):
        """Quiz attempt updates TopicProgress based on score without downgrading higher states."""
        quiz = Quiz.objects.create(classroom=self.classroom1, topic=self.topic, title='Topic Quiz', created_by=self.teacher1)
        q1 = Question.objects.create(quiz=quiz, text='Q1', option_a='A', option_b='B', option_c='C', option_d='D', correct_option='A', order=1)

        attempt_url = f'/api/classrooms/{self.classroom1.id}/quizzes/{quiz.id}/attempt/'

        # Test A: Student 1 scores 100% (>= 70%) -> state becomes COMPLETED
        self.client.force_authenticate(user=self.student1)
        res = self.client.post(attempt_url, {'answers': {str(q1.id): 'A'}}, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        progress1 = TopicProgress.objects.get(student=self.student1, topic=self.topic)
        self.assertEqual(progress1.learning_state, 'COMPLETED')

        # Test B: Student 2 already MASTERED topic; scores 0% on quiz -> stays MASTERED (no downgrade)
        TopicProgress.objects.create(student=self.student2, topic=self.topic, learning_state='MASTERED')
        self.client.force_authenticate(user=self.student2)
        res = self.client.post(attempt_url, {'answers': {str(q1.id): 'B'}}, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        progress2 = TopicProgress.objects.get(student=self.student2, topic=self.topic)
        self.assertEqual(progress2.learning_state, 'MASTERED')

    def test_non_members_404_and_students_forbidden_on_teacher_actions(self):
        """Non-members receive 404 Not Found; active students attempting teacher CRUD get 403 Forbidden."""
        assignment = Assignment.objects.create(classroom=self.classroom1, title='Test Assignment', created_by=self.teacher1)
        quiz = Quiz.objects.create(classroom=self.classroom1, title='Test Quiz', created_by=self.teacher1)

        base_url = f'/api/classrooms/{self.classroom1.id}'

        # 1. Non-member receives 404
        self.client.force_authenticate(user=self.outsider_student)
        self.assertEqual(self.client.get(f'{base_url}/assignments/').status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.get(f'{base_url}/quizzes/').status_code, status.HTTP_404_NOT_FOUND)

        # 2. Student 1 receives 403 on teacher mutation endpoints
        self.client.force_authenticate(user=self.student1)
        self.assertEqual(self.client.post(f'{base_url}/assignments/', {'title': 'X'}).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.delete(f'{base_url}/assignments/{assignment.id}/').status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.post(f'{base_url}/quizzes/', {'title': 'X'}).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.delete(f'{base_url}/quizzes/{quiz.id}/').status_code, status.HTTP_403_FORBIDDEN)

    def test_teacher_can_view_quiz_attempts_students_403_non_members_404(self):
        """Teacher sees all quiz attempts; student receives 403; non-member receives 404."""
        quiz = Quiz.objects.create(classroom=self.classroom1, title='Attempts Test Quiz', created_by=self.teacher1)
        q1 = Question.objects.create(quiz=quiz, text='Q1', option_a='A', option_b='B', option_c='C', option_d='D', correct_option='A', order=1)

        # Student 1 attempts
        QuizAttempt.objects.create(quiz=quiz, student=self.student1, answers={str(q1.id): 'A'}, score=100)

        attempts_url = f'/api/classrooms/{self.classroom1.id}/quizzes/{quiz.id}/attempts/'

        # 1. Teacher sees all attempts (HTTP 200)
        self.client.force_authenticate(user=self.teacher1)
        res_teacher = self.client.get(attempts_url)
        self.assertEqual(res_teacher.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_teacher.data), 1)
        self.assertEqual(res_teacher.data[0]['student_username'], 'student1')

        # 2. Active student gets 403 Forbidden
        self.client.force_authenticate(user=self.student1)
        res_student = self.client.get(attempts_url)
        self.assertEqual(res_student.status_code, status.HTTP_403_FORBIDDEN)

        # 3. Non-member gets 404 Not Found
        self.client.force_authenticate(user=self.outsider_student)
        res_outsider = self.client.get(attempts_url)
        self.assertEqual(res_outsider.status_code, status.HTTP_404_NOT_FOUND)

