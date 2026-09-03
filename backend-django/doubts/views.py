from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied, NotFound, ValidationError
from django.shortcuts import get_object_or_404

from classrooms.models import Classroom, ClassroomMembership
from syllabus.models import Topic
from .models import Doubt, DoubtReply
from .serializers import DoubtSerializer, DoubtDetailSerializer, DoubtReplySerializer
from notifications.services import create_notification
from notifications.models import Notification


def get_validated_classroom(user, classroom_id):
    """
    Validates that the classroom exists and the requesting user is an ACTIVE member of it.
    Raises NotFound (404) if non-member to preserve privacy.
    """
    classroom = get_object_or_404(Classroom, pk=classroom_id)
    is_active_member = classroom.memberships.filter(
        user=user,
        status=ClassroomMembership.MembershipStatus.ACTIVE
    ).exists()

    if not is_active_member:
        raise NotFound("Classroom not found.")

    return classroom


class DoubtListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, classroom_id):
        classroom = get_validated_classroom(request.user, classroom_id)
        doubts = Doubt.objects.filter(classroom=classroom).select_related('author', 'topic')

        topic_param = request.query_params.get('topic')
        if topic_param:
            doubts = doubts.filter(topic_id=topic_param)

        resolved_param = request.query_params.get('resolved')
        if resolved_param is not None:
            resolved_lower = resolved_param.lower()
            if resolved_lower in ('true', '1'):
                doubts = doubts.filter(is_resolved=True)
            elif resolved_lower in ('false', '0'):
                doubts = doubts.filter(is_resolved=False)

        serializer = DoubtSerializer(doubts, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, classroom_id):
        classroom = get_validated_classroom(request.user, classroom_id)
        serializer = DoubtSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        topic_id = serializer.validated_data.get('topic')
        if topic_id:
            if topic_id.module.course.classroom != classroom:
                raise ValidationError({'topic': 'Topic does not belong to this classroom.'})

        doubt = serializer.save(classroom=classroom, author=request.user)
        return Response(DoubtSerializer(doubt).data, status=status.HTTP_201_CREATED)


class DoubtDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, classroom_id, pk):
        classroom = get_validated_classroom(request.user, classroom_id)
        doubt = get_object_or_404(Doubt, pk=pk, classroom=classroom)
        serializer = DoubtDetailSerializer(doubt)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, classroom_id, pk):
        classroom = get_validated_classroom(request.user, classroom_id)
        doubt = get_object_or_404(Doubt, pk=pk, classroom=classroom)

        if doubt.author != request.user:
            raise PermissionDenied("Only the doubt's author can edit this doubt.")

        serializer = DoubtSerializer(doubt, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated_doubt = serializer.save()
        return Response(DoubtSerializer(updated_doubt).data, status=status.HTTP_200_OK)

    def delete(self, request, classroom_id, pk):
        classroom = get_validated_classroom(request.user, classroom_id)
        doubt = get_object_or_404(Doubt, pk=pk, classroom=classroom)

        if doubt.author != request.user and classroom.teacher != request.user:
            raise PermissionDenied("Only the doubt's author or classroom teacher can delete this doubt.")

        doubt.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DoubtReplyListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, classroom_id, doubt_id):
        classroom = get_validated_classroom(request.user, classroom_id)
        doubt = get_object_or_404(Doubt, pk=doubt_id, classroom=classroom)

        serializer = DoubtReplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reply = serializer.save(doubt=doubt, author=request.user)

        if doubt.author != request.user:
            create_notification(
                recipient=doubt.author,
                notification_type=Notification.NotificationType.DOUBT_REPLY,
                message=f"{request.user.username} replied to your doubt: '{doubt.title}'",
                link=f"/classrooms/{classroom.id}/doubts/{doubt.id}"
            )

        return Response(DoubtReplySerializer(reply).data, status=status.HTTP_201_CREATED)


class DoubtReplyAcceptView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, classroom_id, doubt_id, reply_id):
        classroom = get_validated_classroom(request.user, classroom_id)
        doubt = get_object_or_404(Doubt, pk=doubt_id, classroom=classroom)
        reply = get_object_or_404(DoubtReply, pk=reply_id, doubt=doubt)

        if doubt.author != request.user and classroom.teacher != request.user:
            raise PermissionDenied("Only the doubt's author or classroom teacher can accept an answer.")

        # Reset any previously accepted reply for this doubt
        DoubtReply.objects.filter(doubt=doubt, is_accepted_answer=True).update(is_accepted_answer=False)

        reply.is_accepted_answer = True
        reply.save()

        doubt.is_resolved = True
        doubt.save()

        create_notification(
            recipient=reply.author,
            notification_type=Notification.NotificationType.DOUBT_ACCEPTED,
            message=f"Your answer on '{doubt.title}' was marked as accepted!",
            link=f"/classrooms/{classroom.id}/doubts/{doubt.id}"
        )

        return Response(DoubtReplySerializer(reply).data, status=status.HTTP_200_OK)


class DoubtReplyDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, classroom_id, doubt_id, reply_id):
        classroom = get_validated_classroom(request.user, classroom_id)
        doubt = get_object_or_404(Doubt, pk=doubt_id, classroom=classroom)
        reply = get_object_or_404(DoubtReply, pk=reply_id, doubt=doubt)

        if reply.author != request.user and classroom.teacher != request.user:
            raise PermissionDenied("Only the reply's author or classroom teacher can delete this reply.")

        reply.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
