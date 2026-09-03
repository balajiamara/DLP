from classrooms.models import ClassroomMembership
from .models import Notification


def create_notification(recipient, notification_type, message, link):
    """
    Creates a single in-app notification record for a recipient user.
    """
    if not recipient:
        return None

    return Notification.objects.create(
        recipient=recipient,
        notification_type=notification_type,
        message=message,
        link=link
    )


def notify_classroom_students(classroom, notification_type, message, link, exclude_user=None):
    """
    Creates notification records for all active student members of a classroom.
    Optionally excludes a specific user (e.g. sender).
    """
    student_memberships = ClassroomMembership.objects.filter(
        classroom=classroom,
        status=ClassroomMembership.MembershipStatus.ACTIVE,
        role_in_classroom='STUDENT'
    ).select_related('user')

    notifications = []
    for membership in student_memberships:
        user = membership.user
        if exclude_user and user.id == exclude_user.id:
            continue
        notifications.append(
            Notification(
                recipient=user,
                notification_type=notification_type,
                message=message,
                link=link
            )
        )

    if notifications:
        Notification.objects.bulk_create(notifications)

    return len(notifications)
