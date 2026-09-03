import uuid
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied, NotFound
from django.shortcuts import get_object_or_404

from classrooms.models import Classroom, ClassroomMembership
from .models import Course, Module, Topic, Resource, TopicProgress, Material
from .serializers import (
    CourseSerializer,
    CourseDetailSerializer,
    ModuleSerializer,
    TopicSerializer,
    ResourceSerializer,
    TopicProgressSerializer,
    TopicProgressUpdateSerializer,
    MaterialSerializer
)
from .storage import upload_file, get_signed_url, delete_file
from notifications.services import notify_classroom_students
from notifications.models import Notification



def get_validated_classroom(user, classroom_id, require_teacher=False):
    """
    Validates that:
    1. The classroom exists and the user is an ACTIVE member of it.
       If not an active member, raises NotFound (404) for privacy.
    2. If require_teacher=True, validates that the user is the classroom's assigned teacher.
       If active member but not the teacher, raises PermissionDenied (403).
    """
    classroom = get_object_or_404(Classroom, pk=classroom_id)

    is_active_member = classroom.memberships.filter(
        user=user,
        status=ClassroomMembership.MembershipStatus.ACTIVE
    ).exists()

    if not is_active_member:
        raise NotFound("Classroom not found.")

    if require_teacher and classroom.teacher != user:
        raise PermissionDenied("Only the classroom's teacher can modify the syllabus.")

    return classroom


class CourseListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, classroom_id):
        classroom = get_validated_classroom(request.user, classroom_id, require_teacher=False)
        courses = classroom.courses.all()
        serializer = CourseDetailSerializer(courses, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, classroom_id):
        classroom = get_validated_classroom(request.user, classroom_id, require_teacher=True)
        serializer = CourseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        course = serializer.save(classroom=classroom)
        return Response(CourseSerializer(course).data, status=status.HTTP_201_CREATED)


class CourseDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, classroom_id, pk):
        classroom = get_validated_classroom(request.user, classroom_id, require_teacher=False)
        course = get_object_or_404(Course, pk=pk, classroom=classroom)
        serializer = CourseDetailSerializer(course)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, classroom_id, pk):
        classroom = get_validated_classroom(request.user, classroom_id, require_teacher=True)
        course = get_object_or_404(Course, pk=pk, classroom=classroom)
        serializer = CourseSerializer(course, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated_course = serializer.save()
        return Response(CourseSerializer(updated_course).data, status=status.HTTP_200_OK)

    def delete(self, request, classroom_id, pk):
        classroom = get_validated_classroom(request.user, classroom_id, require_teacher=True)
        course = get_object_or_404(Course, pk=pk, classroom=classroom)
        course.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ModuleCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, classroom_id, course_id):
        classroom = get_validated_classroom(request.user, classroom_id, require_teacher=True)
        course = get_object_or_404(Course, pk=course_id, classroom=classroom)
        serializer = ModuleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        module = serializer.save(course=course)
        return Response(ModuleSerializer(module).data, status=status.HTTP_201_CREATED)


class ModuleDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, classroom_id, pk):
        classroom = get_validated_classroom(request.user, classroom_id, require_teacher=True)
        module = get_object_or_404(Module, pk=pk, course__classroom=classroom)
        serializer = ModuleSerializer(module, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated_module = serializer.save()
        return Response(ModuleSerializer(updated_module).data, status=status.HTTP_200_OK)

    def delete(self, request, classroom_id, pk):
        classroom = get_validated_classroom(request.user, classroom_id, require_teacher=True)
        module = get_object_or_404(Module, pk=pk, course__classroom=classroom)
        module.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TopicCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, classroom_id, module_id):
        classroom = get_validated_classroom(request.user, classroom_id, require_teacher=True)
        module = get_object_or_404(Module, pk=module_id, course__classroom=classroom)
        serializer = TopicSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        topic = serializer.save(module=module)
        return Response(TopicSerializer(topic).data, status=status.HTTP_201_CREATED)


class TopicDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, classroom_id, pk):
        classroom = get_validated_classroom(request.user, classroom_id, require_teacher=True)
        topic = get_object_or_404(Topic, pk=pk, module__course__classroom=classroom)
        serializer = TopicSerializer(topic, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated_topic = serializer.save()
        return Response(TopicSerializer(updated_topic).data, status=status.HTTP_200_OK)

    def delete(self, request, classroom_id, pk):
        classroom = get_validated_classroom(request.user, classroom_id, require_teacher=True)
        topic = get_object_or_404(Topic, pk=pk, module__course__classroom=classroom)
        topic.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ResourceCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, classroom_id, topic_id):
        classroom = get_validated_classroom(request.user, classroom_id, require_teacher=True)
        topic = get_object_or_404(Topic, pk=topic_id, module__course__classroom=classroom)
        serializer = ResourceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        resource = serializer.save(topic=topic)
        return Response(ResourceSerializer(resource).data, status=status.HTTP_201_CREATED)


class ResourceDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, classroom_id, pk):
        classroom = get_validated_classroom(request.user, classroom_id, require_teacher=True)
        resource = get_object_or_404(Resource, pk=pk, topic__module__course__classroom=classroom)
        serializer = ResourceSerializer(resource, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated_resource = serializer.save()
        return Response(ResourceSerializer(updated_resource).data, status=status.HTTP_200_OK)

    def delete(self, request, classroom_id, pk):
        classroom = get_validated_classroom(request.user, classroom_id, require_teacher=True)
        resource = get_object_or_404(Resource, pk=pk, topic__module__course__classroom=classroom)
        resource.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class StudentClassroomProgressView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, classroom_id):
        classroom = get_validated_classroom(request.user, classroom_id, require_teacher=False)

        progress_records = TopicProgress.objects.filter(
            student=request.user,
            topic__module__course__classroom=classroom
        )
        progress_map = {p.topic_id: p.learning_state for p in progress_records}

        courses = classroom.courses.prefetch_related('modules__topics')
        result = []
        for course in courses:
            c_data = {
                'id': course.id,
                'title': course.title,
                'modules': []
            }
            for module in course.modules.all():
                m_data = {
                    'id': module.id,
                    'title': module.title,
                    'topics': []
                }
                for topic in module.topics.all():
                    learning_state = progress_map.get(topic.id, TopicProgress.LearningState.NOT_STARTED)
                    m_data['topics'].append({
                        'id': topic.id,
                        'title': topic.title,
                        'learning_state': learning_state
                    })
                c_data['modules'].append(m_data)
            result.append(c_data)

        return Response(result, status=status.HTTP_200_OK)


class TopicProgressUpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, topic_id):
        if request.user.role == 'TEACHER':
            raise PermissionDenied("Progress tracking is student-only.")

        topic = get_object_or_404(Topic, pk=topic_id)
        classroom = topic.module.course.classroom

        is_active_member = classroom.memberships.filter(
            user=request.user,
            status=ClassroomMembership.MembershipStatus.ACTIVE
        ).exists()

        if not is_active_member:
            raise NotFound("Classroom not found.")

        serializer = TopicProgressUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_state = serializer.validated_data['learning_state']

        progress, _ = TopicProgress.objects.update_or_create(
            student=request.user,
            topic=topic,
            defaults={'learning_state': new_state}
        )

        return Response({
            'topic_id': topic.id,
            'learning_state': progress.learning_state,
            'updated_at': progress.updated_at
        }, status=status.HTTP_200_OK)


class StudentProgressSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, classroom_id):
        classroom = get_validated_classroom(request.user, classroom_id, require_teacher=False)

        topics = Topic.objects.filter(module__course__classroom=classroom)
        total_topics = topics.count()

        progress_records = TopicProgress.objects.filter(
            student=request.user,
            topic__module__course__classroom=classroom
        )
        progress_map = {p.topic_id: p.learning_state for p in progress_records}

        all_states = [choice[0] for choice in TopicProgress.LearningState.choices]
        by_state = {state: 0 for state in all_states}

        for topic in topics:
            state = progress_map.get(topic.id, TopicProgress.LearningState.NOT_STARTED)
            by_state[state] += 1

        completed_or_mastered = by_state['COMPLETED'] + by_state['MASTERED']
        percent_complete = round((completed_or_mastered / total_topics * 100), 2) if total_topics > 0 else 0.0

        return Response({
            'total_topics': total_topics,
            'completed_or_mastered_topics': completed_or_mastered,
            'by_state': by_state,
            'state_breakdown': by_state,
            'percent_complete': percent_complete
        }, status=status.HTTP_200_OK)


class TopicMaterialListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, topic_id):
        topic = get_object_or_404(Topic, pk=topic_id)
        classroom = topic.module.course.classroom

        is_active_member = classroom.memberships.filter(
            user=request.user,
            status=ClassroomMembership.MembershipStatus.ACTIVE
        ).exists()

        if not is_active_member:
            raise NotFound("Classroom not found.")

        materials = topic.materials.all()
        serializer = MaterialSerializer(materials, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, topic_id):
        topic = get_object_or_404(Topic, pk=topic_id)
        classroom = topic.module.course.classroom

        is_active_member = classroom.memberships.filter(
            user=request.user,
            status=ClassroomMembership.MembershipStatus.ACTIVE
        ).exists()

        if not is_active_member:
            raise NotFound("Classroom not found.")

        if classroom.teacher != request.user:
            raise PermissionDenied("Only the classroom's teacher can upload materials.")

        if 'file' not in request.FILES:
            return Response({'detail': 'No file was provided.'}, status=status.HTTP_400_BAD_REQUEST)

        file_obj = request.FILES['file']
        ALLOWED_EXTENSIONS = {'pdf', 'docx', 'pptx', 'png', 'jpg', 'jpeg'}
        ext = file_obj.name.split('.')[-1].lower() if '.' in file_obj.name else ''
        if ext not in ALLOWED_EXTENSIONS:
            return Response(
                {'detail': f'File extension .{ext} is not allowed. Allowed extensions: pdf, docx, pptx, png, jpg, jpeg.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        MAX_SIZE = 20 * 1024 * 1024  # 20MB
        if file_obj.size > MAX_SIZE:
            return Response(
                {'detail': 'File size exceeds maximum limit of 20MB.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        title = request.data.get('title') or file_obj.name
        storage_path = f"classroom_{classroom.id}/topic_{topic.id}/{uuid.uuid4()}_{file_obj.name}"

        file_bytes = file_obj.read()
        try:
            upload_file(storage_path, file_bytes, content_type=file_obj.content_type or 'application/octet-stream')
        except Exception as upload_err:
            return Response({'detail': f'Storage upload failed: {str(upload_err)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            material = Material.objects.create(
                topic=topic,
                uploaded_by=request.user,
                title=title,
                file_name=file_obj.name,
                storage_path=storage_path,
                file_type=ext,
                file_size_bytes=file_obj.size,
                status=Material.MaterialStatus.UPLOADED
            )
        except Exception as db_err:
            try:
                delete_file(storage_path)
            except Exception:
                pass
            raise db_err

        notify_classroom_students(
            classroom=classroom,
            notification_type=Notification.NotificationType.NEW_MATERIAL,
            message=f"New material posted in {topic.title}: {material.title}",
            link=f"/classrooms/{classroom.id}/materials",
            exclude_user=request.user
        )

        return Response(MaterialSerializer(material).data, status=status.HTTP_201_CREATED)


class MaterialDownloadURLView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        material = get_object_or_404(Material, pk=pk)
        classroom = material.topic.module.course.classroom

        is_active_member = classroom.memberships.filter(
            user=request.user,
            status=ClassroomMembership.MembershipStatus.ACTIVE
        ).exists()

        if not is_active_member:
            raise NotFound("Classroom not found.")

        signed_url = get_signed_url(material.storage_path, expires_in=3600)
        return Response({
            'download_url': signed_url,
            'expires_in': 3600
        }, status=status.HTTP_200_OK)


class MaterialDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, pk):
        material = get_object_or_404(Material, pk=pk)
        classroom = material.topic.module.course.classroom

        is_active_member = classroom.memberships.filter(
            user=request.user,
            status=ClassroomMembership.MembershipStatus.ACTIVE
        ).exists()

        if not is_active_member:
            raise NotFound("Classroom not found.")

        if classroom.teacher != request.user:
            raise PermissionDenied("Only the classroom's teacher can delete materials.")

        try:
            delete_file(material.storage_path)
        except Exception:
            pass

        material.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


