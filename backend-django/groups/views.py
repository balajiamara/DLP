from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import NotFound, PermissionDenied
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model

from .models import Group, GroupMembership
from .serializers import GroupSerializer, GroupCreateSerializer

User = get_user_model()


class GroupListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return GroupCreateSerializer
        return GroupSerializer

    def get_queryset(self):
        return Group.objects.filter(
            memberships__user=self.request.user,
            memberships__status=GroupMembership.MembershipStatus.ACTIVE
        ).distinct().order_by('-created_at')

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        group = serializer.save()

        output_serializer = GroupSerializer(group, context={'request': request})
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


class GroupDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = GroupSerializer

    def get_object(self):
        group_id = self.kwargs.get('pk')
        group = get_object_or_404(Group, pk=group_id)

        is_active_member = group.memberships.filter(
            user=self.request.user,
            status=GroupMembership.MembershipStatus.ACTIVE
        ).exists()

        if not is_active_member:
            raise NotFound("Group not found.")

        return group


class AddGroupMemberView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        group = get_object_or_404(Group, pk=pk)

        # Check if requesting user is an active member
        is_active_member = group.memberships.filter(
            user=request.user,
            status=GroupMembership.MembershipStatus.ACTIVE
        ).exists()

        if not is_active_member:
            raise NotFound("Group not found.")

        user_id = request.data.get('user_id')
        username = request.data.get('username')

        target_user = None
        if user_id:
            target_user = User.objects.filter(pk=user_id).first()
        elif username:
            target_user = User.objects.filter(username__iexact=str(username).strip()).first()

        if not target_user:
            return Response({'error': 'Target user not found.'}, status=status.HTTP_404_NOT_FOUND)

        membership, created = GroupMembership.objects.get_or_create(
            user=target_user,
            group=group,
            defaults={'status': GroupMembership.MembershipStatus.ACTIVE}
        )

        if not created:
            if membership.status == GroupMembership.MembershipStatus.ACTIVE:
                return Response(
                    {'detail': 'User is already an active member of this group.'},
                    status=status.HTTP_200_OK
                )
            else:
                membership.status = GroupMembership.MembershipStatus.ACTIVE
                membership.save()
                return Response(
                    {'detail': 'User added to group successfully.'},
                    status=status.HTTP_200_OK
                )

        return Response(
            {'detail': 'User added to group successfully.'},
            status=status.HTTP_201_CREATED
        )


class LeaveGroupView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        group = get_object_or_404(Group, pk=pk)

        membership = group.memberships.filter(
            user=request.user,
            status=GroupMembership.MembershipStatus.ACTIVE
        ).first()

        if not membership:
            raise NotFound("Group not found.")

        membership.status = GroupMembership.MembershipStatus.REMOVED
        membership.save()

        return Response(
            {'detail': 'Successfully left the group.'},
            status=status.HTTP_200_OK
        )
