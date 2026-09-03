from unittest.mock import patch, MagicMock
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase
from rest_framework import status
from classrooms.models import Classroom, ClassroomMembership
from .models import Course, Module, Topic, Resource, TopicProgress, Material

User = get_user_model()



class SyllabusAPITests(APITestCase):
    def setUp(self):
        # Teacher 1 (Owner of Classroom 1)
        self.teacher1 = User.objects.create_user(
            email='teacher1@example.com',
            username='teacher1',
            password='Password123!',
            role='TEACHER'
        )
        self.classroom1 = Classroom.objects.create(
            name='Classroom 1',
            description='Physics Class',
            teacher=self.teacher1
        )
        ClassroomMembership.objects.create(
            user=self.teacher1,
            classroom=self.classroom1,
            role_in_classroom='TEACHER',
            status=ClassroomMembership.MembershipStatus.ACTIVE
        )

        # Student 1 (Active member of Classroom 1)
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

        # Student 2 (Active member of Classroom 1)
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

        # Teacher 2 (Not a member of Classroom 1)
        self.teacher2 = User.objects.create_user(
            email='teacher2@example.com',
            username='teacher2',
            password='Password123!',
            role='TEACHER'
        )
        self.classroom2 = Classroom.objects.create(
            name='Classroom 2',
            description='Math Class',
            teacher=self.teacher2
        )
        ClassroomMembership.objects.create(
            user=self.teacher2,
            classroom=self.classroom2,
            role_in_classroom='TEACHER',
            status=ClassroomMembership.MembershipStatus.ACTIVE
        )

        # Non-member Student (Not a member of Classroom 1)
        self.outsider_student = User.objects.create_user(
            email='outsider@example.com',
            username='outsider',
            password='Password123!',
            role='STUDENT'
        )

    def test_teacher_can_build_full_syllabus_tree(self):
        """Teacher 1 builds a complete Course -> Module -> Topic -> Resource tree via API."""
        self.client.force_authenticate(user=self.teacher1)

        # 1. Create Course
        course_url = f'/api/classrooms/{self.classroom1.id}/courses/'
        response = self.client.post(course_url, {'title': 'Quantum Mechanics', 'description': 'Introductory Course', 'order': 1})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        course_id = response.data['id']
        self.assertEqual(response.data['title'], 'Quantum Mechanics')

        # 2. Create Module
        module_url = f'/api/classrooms/{self.classroom1.id}/courses/{course_id}/modules/'
        response = self.client.post(module_url, {'title': 'Module 1: Fundamentals', 'description': 'Wave functions', 'order': 1})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        module_id = response.data['id']

        # 3. Create Topic
        topic_url = f'/api/classrooms/{self.classroom1.id}/modules/{module_id}/topics/'
        response = self.client.post(topic_url, {'title': 'Topic 1.1: Schrodinger Equation', 'order': 1})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        topic_id = response.data['id']

        # 4. Create Resource
        resource_url = f'/api/classrooms/{self.classroom1.id}/topics/{topic_id}/resources/'
        response = self.client.post(resource_url, {
            'title': 'Lecture Notes PDF',
            'resource_type': 'NOTE',
            'url_or_note': 'Schrodinger equation derivations',
            'order': 1
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        resource_id = response.data['id']

        # 5. Retrieve Full Nested Tree via GET /api/classrooms/<id>/courses/<course_id>/
        detail_url = f'/api/classrooms/{self.classroom1.id}/courses/{course_id}/'
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.data
        self.assertEqual(data['id'], course_id)
        self.assertEqual(data['title'], 'Quantum Mechanics')
        self.assertEqual(len(data['modules']), 1)
        self.assertEqual(data['modules'][0]['id'], module_id)
        self.assertEqual(len(data['modules'][0]['topics']), 1)
        self.assertEqual(data['modules'][0]['topics'][0]['id'], topic_id)
        self.assertEqual(len(data['modules'][0]['topics'][0]['resources']), 1)
        self.assertEqual(data['modules'][0]['topics'][0]['resources'][0]['id'], resource_id)
        self.assertEqual(data['modules'][0]['topics'][0]['resources'][0]['resource_type'], 'NOTE')

    def test_student_can_view_tree_but_cannot_mutate(self):
        """Active student member can GET courses/tree, but gets 403 on POST, PATCH, DELETE."""
        # Create course hierarchy as Teacher 1 first
        course = Course.objects.create(classroom=self.classroom1, title='Classical Mechanics', order=1)
        module = Module.objects.create(course=course, title='Kinematics', order=1)
        topic = Topic.objects.create(module=module, title='Vectors', order=1)
        resource = Resource.objects.create(topic=topic, title='Vector Math', resource_type='LINK', url_or_note='https://example.com')

        # Authenticate as Student 1 (active member of classroom1)
        self.client.force_authenticate(user=self.student1)

        # GET course list -> 200 OK
        list_url = f'/api/classrooms/{self.classroom1.id}/courses/'
        response = self.client.get(list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

        # GET course detail -> 200 OK
        detail_url = f'/api/classrooms/{self.classroom1.id}/courses/{course.id}/'
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Classical Mechanics')

        # POST course -> 403 Forbidden
        response = self.client.post(list_url, {'title': 'Unauthorized Course'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # POST module -> 403 Forbidden
        module_url = f'/api/classrooms/{self.classroom1.id}/courses/{course.id}/modules/'
        response = self.client.post(module_url, {'title': 'Unauthorized Module'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # PATCH course -> 403 Forbidden
        response = self.client.patch(detail_url, {'title': 'Hacked Title'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # DELETE course -> 403 Forbidden
        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # PATCH resource -> 403 Forbidden
        resource_url = f'/api/classrooms/{self.classroom1.id}/resources/{resource.id}/'
        response = self.client.patch(resource_url, {'title': 'Hacked Resource'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_member_receives_404(self):
        """Non-members (both student and teacher of another classroom) receive 404 Not Found."""
        course = Course.objects.create(classroom=self.classroom1, title='Thermodynamics', order=1)

        # 1. Outsider student (not a member of classroom1)
        self.client.force_authenticate(user=self.outsider_student)

        list_url = f'/api/classrooms/{self.classroom1.id}/courses/'
        self.assertEqual(self.client.get(list_url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.post(list_url, {'title': 'New Course'}).status_code, status.HTTP_404_NOT_FOUND)

        detail_url = f'/api/classrooms/{self.classroom1.id}/courses/{course.id}/'
        self.assertEqual(self.client.get(detail_url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.patch(detail_url, {'title': 'Mod'}).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.delete(detail_url).status_code, status.HTTP_404_NOT_FOUND)

        # 2. Teacher 2 (teacher of classroom2, NOT a member of classroom1)
        self.client.force_authenticate(user=self.teacher2)

        self.assertEqual(self.client.get(list_url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.post(list_url, {'title': 'New Course'}).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.get(detail_url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.patch(detail_url, {'title': 'Mod'}).status_code, status.HTTP_404_NOT_FOUND)

    def test_teacher_updates_and_deletes_items(self):
        """Teacher 1 can update (PATCH) and delete (DELETE) courses, modules, topics, resources."""
        self.client.force_authenticate(user=self.teacher1)

        course = Course.objects.create(classroom=self.classroom1, title='Electromagnetism', order=1)
        module = Module.objects.create(course=course, title='Electrostatics', order=1)
        topic = Topic.objects.create(module=module, title='Gauss Law', order=1)
        resource = Resource.objects.create(topic=topic, title='Diagram', resource_type='LINK', url_or_note='http://test.com')

        # Patch Resource
        resource_url = f'/api/classrooms/{self.classroom1.id}/resources/{resource.id}/'
        response = self.client.patch(resource_url, {'title': 'Updated Diagram'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Updated Diagram')

        # Delete Resource
        response = self.client.delete(resource_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Resource.objects.filter(id=resource.id).exists())

        # Delete Topic
        topic_url = f'/api/classrooms/{self.classroom1.id}/topics/{topic.id}/'
        response = self.client.delete(topic_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Topic.objects.filter(id=topic.id).exists())

        # Delete Module
        module_url = f'/api/classrooms/{self.classroom1.id}/modules/{module.id}/'
        response = self.client.delete(module_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Module.objects.filter(id=module.id).exists())

        # Delete Course
        course_url = f'/api/classrooms/{self.classroom1.id}/courses/{course.id}/'
        response = self.client.delete(course_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Course.objects.filter(id=course.id).exists())

    # --- Progress Tracking Tests ---

    def test_student_progress_set_and_persists(self):
        """Student sets progress on a topic and it persists across PATCH and GET."""
        course = Course.objects.create(classroom=self.classroom1, title='Optics', order=1)
        module = Module.objects.create(course=course, title='Refraction', order=1)
        topic = Topic.objects.create(module=module, title='Snell Law', order=1)

        self.client.force_authenticate(user=self.student1)

        # 1. Update topic progress via PATCH /api/topics/<id>/my-progress/
        update_url = f'/api/topics/{topic.id}/my-progress/'
        response = self.client.patch(update_url, {'learning_state': 'PRACTICING'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['learning_state'], 'PRACTICING')

        # 2. Verify persistence via GET /api/classrooms/<id>/my-progress/
        progress_url = f'/api/classrooms/{self.classroom1.id}/my-progress/'
        response = self.client.get(progress_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        topic_state = response.data[0]['modules'][0]['topics'][0]['learning_state']
        self.assertEqual(topic_state, 'PRACTICING')

    def test_student_progress_defaults_to_not_started(self):
        """Student progress defaults to NOT_STARTED for untouched topics."""
        course = Course.objects.create(classroom=self.classroom1, title='Nuclear Physics', order=1)
        module = Module.objects.create(course=course, title='Fission', order=1)
        Topic.objects.create(module=module, title='Chain Reactions', order=1)

        self.client.force_authenticate(user=self.student1)

        progress_url = f'/api/classrooms/{self.classroom1.id}/my-progress/'
        response = self.client.get(progress_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        topic_state = response.data[0]['modules'][0]['topics'][0]['learning_state']
        self.assertEqual(topic_state, 'NOT_STARTED')

    def test_teacher_cannot_set_progress_on_own_account(self):
        """A teacher attempting to set topic progress on their own account gets 403 Forbidden."""
        course = Course.objects.create(classroom=self.classroom1, title='Astrophysics', order=1)
        module = Module.objects.create(course=course, title='Stars', order=1)
        topic = Topic.objects.create(module=module, title='Supernovae', order=1)

        self.client.force_authenticate(user=self.teacher1)

        update_url = f'/api/topics/{topic.id}/my-progress/'
        response = self.client.patch(update_url, {'learning_state': 'COMPLETED'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_member_cannot_view_or_update_progress(self):
        """A non-member receives 404 Not Found on both view and update progress endpoints."""
        course = Course.objects.create(classroom=self.classroom1, title='Relativity', order=1)
        module = Module.objects.create(course=course, title='Special Relativity', order=1)
        topic = Topic.objects.create(module=module, title='Time Dilation', order=1)

        self.client.force_authenticate(user=self.outsider_student)

        progress_url = f'/api/classrooms/{self.classroom1.id}/my-progress/'
        self.assertEqual(self.client.get(progress_url).status_code, status.HTTP_404_NOT_FOUND)

        summary_url = f'/api/classrooms/{self.classroom1.id}/progress-summary/'
        self.assertEqual(self.client.get(summary_url).status_code, status.HTTP_404_NOT_FOUND)

        update_url = f'/api/topics/{topic.id}/my-progress/'
        self.assertEqual(self.client.patch(update_url, {'learning_state': 'LEARNING'}).status_code, status.HTTP_404_NOT_FOUND)

    def test_percent_complete_calculation(self):
        """Aggregate summary correctly calculates percent_complete across a mix of states."""
        course = Course.objects.create(classroom=self.classroom1, title='Fluid Mechanics', order=1)
        module = Module.objects.create(course=course, title='Dynamics', order=1)
        t1 = Topic.objects.create(module=module, title='Bernoulli', order=1)
        t2 = Topic.objects.create(module=module, title='Continuity', order=2)
        t3 = Topic.objects.create(module=module, title='Viscosity', order=3)
        t4 = Topic.objects.create(module=module, title='Turbulence', order=4)

        # Set 1 COMPLETED, 1 MASTERED, 1 LEARNING, 1 untouched (NOT_STARTED)
        TopicProgress.objects.create(student=self.student1, topic=t1, learning_state='COMPLETED')
        TopicProgress.objects.create(student=self.student1, topic=t2, learning_state='MASTERED')
        TopicProgress.objects.create(student=self.student1, topic=t3, learning_state='LEARNING')

        self.client.force_authenticate(user=self.student1)

        summary_url = f'/api/classrooms/{self.classroom1.id}/progress-summary/'
        response = self.client.get(summary_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.data
        self.assertEqual(data['total_topics'], 4)
        self.assertEqual(data['by_state']['COMPLETED'], 1)
        self.assertEqual(data['by_state']['MASTERED'], 1)
        self.assertEqual(data['by_state']['LEARNING'], 1)
        self.assertEqual(data['by_state']['NOT_STARTED'], 1)
        # 2 out of 4 topics completed/mastered = 50.0%
        self.assertEqual(data['percent_complete'], 50.0)

    def test_progress_scoped_per_student(self):
        """Student A's progress updates do not leak into or affect Student B's view."""
        course = Course.objects.create(classroom=self.classroom1, title='Quantum Computing', order=1)
        module = Module.objects.create(course=course, title='Qubits', order=1)
        topic = Topic.objects.create(module=module, title='Superposition', order=1)

        # Student 1 marks topic as MASTERED
        TopicProgress.objects.create(student=self.student1, topic=topic, learning_state='MASTERED')

        # Authenticate as Student 2 (also an active member of classroom 1)
        self.client.force_authenticate(user=self.student2)

        # Check Student 2 progress tree -> defaults to NOT_STARTED
        progress_url = f'/api/classrooms/{self.classroom1.id}/my-progress/'
        response = self.client.get(progress_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        student2_state = response.data[0]['modules'][0]['topics'][0]['learning_state']
        self.assertEqual(student2_state, 'NOT_STARTED')

        # Check Student 2 summary -> percent_complete is 0.0
        summary_url = f'/api/classrooms/{self.classroom1.id}/progress-summary/'
        response = self.client.get(summary_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['percent_complete'], 0.0)

    # --- Material & Supabase Storage Tests ---

    @patch('syllabus.views.upload_file')
    def test_teacher_can_upload_valid_material(self, mock_upload):
        """Teacher uploads a valid PDF material, stored with status=UPLOADED."""
        course = Course.objects.create(classroom=self.classroom1, title='Computer Science', order=1)
        module = Module.objects.create(course=course, title='Algorithms', order=1)
        topic = Topic.objects.create(module=module, title='Sorting', order=1)

        self.client.force_authenticate(user=self.teacher1)

        pdf_file = SimpleUploadedFile("sorting_notes.pdf", b"%PDF-1.4 content", content_type="application/pdf")
        upload_url = f'/api/topics/{topic.id}/materials/'

        response = self.client.post(upload_url, {'file': pdf_file, 'title': 'Sorting Lecture Notes'}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['title'], 'Sorting Lecture Notes')
        self.assertEqual(response.data['file_type'], 'pdf')
        self.assertEqual(response.data['status'], 'UPLOADED')

        mock_upload.assert_called_once()
        self.assertTrue(Material.objects.filter(topic=topic, file_name='sorting_notes.pdf').exists())

    def test_upload_rejects_disallowed_and_oversized_files(self):
        """Upload rejects disallowed file extensions (.exe) and oversized files (>20MB)."""
        course = Course.objects.create(classroom=self.classroom1, title='Cybersecurity', order=1)
        module = Module.objects.create(course=course, title='Malware', order=1)
        topic = Topic.objects.create(module=module, title='Executables', order=1)

        self.client.force_authenticate(user=self.teacher1)
        upload_url = f'/api/topics/{topic.id}/materials/'

        # 1. Disallowed extension .exe
        exe_file = SimpleUploadedFile("payload.exe", b"binary content", content_type="application/x-msdownload")
        response = self.client.post(upload_url, {'file': exe_file}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('not allowed', response.data['detail'])

        # 2. Oversized file (>20MB)
        large_content = b"0" * (21 * 1024 * 1024)
        large_file = SimpleUploadedFile("big_book.pdf", large_content, content_type="application/pdf")
        response = self.client.post(upload_url, {'file': large_file}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('exceeds maximum limit', response.data['detail'])

    def test_student_cannot_upload_material(self):
        """Student attempting to upload material receives 403 Forbidden."""
        course = Course.objects.create(classroom=self.classroom1, title='History', order=1)
        module = Module.objects.create(course=course, title='Ancient', order=1)
        topic = Topic.objects.create(module=module, title='Egypt', order=1)

        self.client.force_authenticate(user=self.student1)
        upload_url = f'/api/topics/{topic.id}/materials/'

        pdf_file = SimpleUploadedFile("history.pdf", b"pdf content", content_type="application/pdf")
        response = self.client.post(upload_url, {'file': pdf_file}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch('syllabus.views.get_signed_url', return_value='https://supabase.co/storage/v1/object/sign/materials/test.pdf?token=abc')
    def test_active_member_can_list_and_get_download_url(self, mock_signed_url):
        """Active classroom member (student) can list topic materials and get signed download URLs."""
        course = Course.objects.create(classroom=self.classroom1, title='Biology', order=1)
        module = Module.objects.create(course=course, title='Genetics', order=1)
        topic = Topic.objects.create(module=module, title='DNA', order=1)

        material = Material.objects.create(
            topic=topic,
            uploaded_by=self.teacher1,
            title='DNA Diagram',
            file_name='dna.png',
            storage_path='classroom_1/topic_1/dna.png',
            file_type='png',
            file_size_bytes=1024,
            status='UPLOADED'
        )

        self.client.force_authenticate(user=self.student1)

        # 1. List materials for topic
        list_url = f'/api/topics/{topic.id}/materials/'
        response = self.client.get(list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['title'], 'DNA Diagram')

        # 2. Get signed download URL
        download_url = f'/api/materials/{material.id}/download-url/'
        response = self.client.get(download_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['download_url'], 'https://supabase.co/storage/v1/object/sign/materials/test.pdf?token=abc')
        mock_signed_url.assert_called_once_with('classroom_1/topic_1/dna.png', expires_in=3600)

    def test_non_member_cannot_access_materials(self):
        """Non-member receives 404 Not Found across material endpoints."""
        course = Course.objects.create(classroom=self.classroom1, title='Chemistry', order=1)
        module = Module.objects.create(course=course, title='Organic', order=1)
        topic = Topic.objects.create(module=module, title='Alkanes', order=1)

        material = Material.objects.create(
            topic=topic,
            uploaded_by=self.teacher1,
            title='Alkane Chart',
            file_name='alkane.png',
            storage_path='classroom_1/topic_1/alkane.png',
            file_type='png',
            file_size_bytes=512,
            status='UPLOADED'
        )

        self.client.force_authenticate(user=self.outsider_student)

        list_url = f'/api/topics/{topic.id}/materials/'
        self.assertEqual(self.client.get(list_url).status_code, status.HTTP_404_NOT_FOUND)

        download_url = f'/api/materials/{material.id}/download-url/'
        self.assertEqual(self.client.get(download_url).status_code, status.HTTP_404_NOT_FOUND)

        delete_url = f'/api/materials/{material.id}/'
        self.assertEqual(self.client.delete(delete_url).status_code, status.HTTP_404_NOT_FOUND)

    @patch('syllabus.views.delete_file')
    def test_teacher_can_delete_material(self, mock_delete):
        """Teacher can delete a material, triggering Supabase object removal and DB row deletion."""
        course = Course.objects.create(classroom=self.classroom1, title='Physics II', order=1)
        module = Module.objects.create(course=course, title='Circuits', order=1)
        topic = Topic.objects.create(module=module, title='Resistors', order=1)

        material = Material.objects.create(
            topic=topic,
            uploaded_by=self.teacher1,
            title='Circuit Diagram',
            file_name='circuit.png',
            storage_path='classroom_1/topic_1/circuit.png',
            file_type='png',
            file_size_bytes=2048,
            status='UPLOADED'
        )

        self.client.force_authenticate(user=self.teacher1)

        delete_url = f'/api/materials/{material.id}/'
        response = self.client.delete(delete_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        mock_delete.assert_called_once_with('classroom_1/topic_1/circuit.png')
        self.assertFalse(Material.objects.filter(id=material.id).exists())

    @patch('syllabus.views.upload_file')
    @patch('syllabus.views.delete_file')
    def test_storage_cleaned_up_on_db_failure(self, mock_delete, mock_upload):
        """If DB record creation fails after successful storage upload, uploaded file gets cleaned up."""
        course = Course.objects.create(classroom=self.classroom1, title='Database Systems', order=1)
        module = Module.objects.create(course=course, title='SQL', order=1)
        topic = Topic.objects.create(module=module, title='Indexes', order=1)

        self.client.force_authenticate(user=self.teacher1)
        upload_url = f'/api/topics/{topic.id}/materials/'
        pdf_file = SimpleUploadedFile("db_notes.pdf", b"pdf data", content_type="application/pdf")

        # Mock Material.objects.create to raise a database exception
        with patch.object(Material.objects, 'create', side_effect=Exception("Database Connection Error")):
            with self.assertRaises(Exception):
                self.client.post(upload_url, {'file': pdf_file, 'title': 'SQL Indexes'}, format='multipart')

        # Verify storage upload happened AND cleanup delete_file was called
        mock_upload.assert_called_once()
        mock_delete.assert_called_once()


