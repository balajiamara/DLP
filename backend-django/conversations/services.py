from .models import Conversation
from classrooms.models import ClassroomMembership
from groups.models import GroupMembership


def get_or_create_classroom_conversation(classroom):
    conv, _ = Conversation.objects.get_or_create(
        classroom=classroom,
        type=Conversation.Type.CLASSROOM
    )
    return conv


def get_or_create_group_conversation(group):
    conv, _ = Conversation.objects.get_or_create(
        group=group,
        type=Conversation.Type.GROUP
    )
    return conv


def check_conversation_access(user, conversation) -> bool:
    """
    Checks if a user is authorized to participate in a conversation.
    - CLASSROOM: must be an active ClassroomMembership.
    - GROUP: must be an active GroupMembership.
    - DIRECT: must be user_a or user_b.
    """
    if not user or not user.is_authenticated:
        return False

    if conversation.type == Conversation.Type.CLASSROOM:
        if not conversation.classroom_id:
            return False
        return conversation.classroom.memberships.filter(
            user=user,
            status=ClassroomMembership.MembershipStatus.ACTIVE
        ).exists()

    elif conversation.type == Conversation.Type.GROUP:
        if not conversation.group_id:
            return False
        return conversation.group.memberships.filter(
            user=user,
            status=GroupMembership.MembershipStatus.ACTIVE
        ).exists()

    elif conversation.type == Conversation.Type.DIRECT:
        return user.id in (conversation.user_a_id, conversation.user_b_id)

    return False
