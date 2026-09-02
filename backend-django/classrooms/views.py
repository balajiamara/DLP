from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied, NotFound
from django.shortcuts import get_object_or_404

from .models import Classroom, ClassroomMembership, JoinToken
from .serializers import ClassroomSerializer, ClassroomCreateSerializer


class ClassroomListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ClassroomCreateSerializer
        return ClassroomSerializer

    def get_queryset(self):
        return Classroom.objects.filter(
            memberships__user=self.request.user,
            memberships__status=ClassroomMembership.MembershipStatus.ACTIVE
        ).distinct().order_by('-created_at')

    def create(self, request, *args, **kwargs):
        if request.user.role != 'TEACHER':
            raise PermissionDenied("Only teachers can create classrooms.")

        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        classroom = serializer.save()

        output_serializer = ClassroomSerializer(classroom, context={'request': request})
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


class ClassroomDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ClassroomSerializer

    def get_object(self):
        classroom_id = self.kwargs.get('pk')
        classroom = get_object_or_404(Classroom, pk=classroom_id)

        # Check if requesting user is an active member
        is_active_member = classroom.memberships.filter(
            user=self.request.user,
            status=ClassroomMembership.MembershipStatus.ACTIVE
        ).exists()

        if not is_active_member:
            raise NotFound("Classroom not found.")

        # For write operations (PATCH, PUT, DELETE), enforce owner/teacher permission
        if self.request.method in ['PATCH', 'PUT', 'DELETE']:
            if classroom.teacher != self.request.user:
                raise PermissionDenied("Only the classroom's assigned teacher can modify or delete this classroom.")

        return classroom


class CreateJoinTokenView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        classroom = get_object_or_404(Classroom, pk=pk)

        # Check if requesting user is an active member
        is_active_member = classroom.memberships.filter(
            user=request.user,
            status=ClassroomMembership.MembershipStatus.ACTIVE
        ).exists()

        if not is_active_member:
            raise NotFound("Classroom not found.")

        if classroom.teacher != request.user:
            raise PermissionDenied("Only the classroom's assigned teacher can generate join tokens.")

        join_token = JoinToken.objects.create(
            classroom=classroom,
            created_by=request.user
        )
        return Response(
            {
                'token': join_token.token,
                'classroom_id': classroom.id,
                'created_at': join_token.created_at
            },
            status=status.HTTP_201_CREATED
        )


class JoinClassroomView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, token):
        join_token = JoinToken.objects.filter(token=token).select_related('classroom').first()
        if not join_token:
            raise NotFound("Invalid or non-existent join token.")

        classroom = join_token.classroom
        membership, created = ClassroomMembership.objects.get_or_create(
            user=request.user,
            classroom=classroom,
            defaults={
                'role_in_classroom': request.user.role,
                'status': ClassroomMembership.MembershipStatus.ACTIVE
            }
        )

        if not created:
            if membership.status == ClassroomMembership.MembershipStatus.ACTIVE:
                return Response(
                    {
                        'detail': 'Already a member of this classroom.',
                        'classroom_id': classroom.id
                    },
                    status=status.HTTP_200_OK
                )
            else:
                membership.status = ClassroomMembership.MembershipStatus.ACTIVE
                membership.role_in_classroom = request.user.role
                membership.save()
                return Response(
                    {
                        'detail': 'Rejoined classroom successfully.',
                        'classroom_id': classroom.id
                    },
                    status=status.HTTP_200_OK
                )

        return Response(
            {
                'detail': 'Successfully joined classroom.',
                'classroom_id': classroom.id
            },
            status=status.HTTP_201_CREATED
        )
