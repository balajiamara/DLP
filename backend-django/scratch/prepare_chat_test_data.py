import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dlp_core.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from classrooms.models import Classroom, ClassroomMembership
from groups.models import Group, GroupMembership
from conversations.models import Conversation, Message

User = get_user_model()

teacher = User.objects.get(username='tester')
student = User.objects.get(username='tester2')
student3 = User.objects.get(username='test3')

# 1. Prepare Classroom 6 pagination data
conv_6 = Conversation.objects.get(id=6)
current_count = conv_6.messages.count()
print(f"Current message count in Classroom 6: {current_count}")

# Seed up to 35 messages if fewer than 35
if current_count < 35:
    now = timezone.now()
    needed = 35 - current_count
    print(f"Seeding {needed} historical messages in Classroom 6...")
    new_messages = []
    for i in range(needed):
        # Spaced in the past so order is strictly chronological
        ts = now - timedelta(minutes=(needed - i) * 10)
        sender = teacher if i % 2 == 0 else student
        msg = Message(
            conversation=conv_6,
            sender=sender,
            body=f"Historical discussion note #{i + 1}: Reviewing Chapter {((i % 5) + 1)} concepts.",
            created_at=ts
        )
        new_messages.append(msg)
    Message.objects.bulk_create(new_messages)
    print(f"Seeded! Total messages now: {conv_6.messages.count()}")

# 2. Prepare Fresh Study Group for Empty State Verification
group, created = Group.objects.get_or_create(
    name="Algorithms Peer Group",
    defaults={
        "description": "Collaborative study group for data structures and algorithms.",
        "created_by": student,
    }
)

# Ensure memberships
GroupMembership.objects.get_or_create(
    group=group,
    user=student,
    defaults={"status": GroupMembership.MembershipStatus.ACTIVE}
)
GroupMembership.objects.get_or_create(
    group=group,
    user=teacher,
    defaults={"status": GroupMembership.MembershipStatus.ACTIVE}
)

# Ensure Conversation provisioned
group_conv, conv_created = Conversation.objects.get_or_create(
    group=group,
    type=Conversation.Type.GROUP
)

print(f"Study Group: ID={group.id}, Name='{group.name}', ConversationID={group_conv.id}, Messages={group_conv.messages.count()}")
