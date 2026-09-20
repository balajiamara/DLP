"""
Conversation Authorization Service

Provides read-only cross-service authorization checks for conversations.
Validates that a connecting user has active access to a specific Conversation (CLASSROOM, GROUP, DIRECT).
"""

import logging
from sqlalchemy import select, Table, Column, BigInteger, String
from app.db.session import async_session_maker
from app.db.models import Base

logger = logging.getLogger(__name__)

conversations_conversation = Table(
    "conversations_conversation",
    Base.metadata,
    Column("id", BigInteger, primary_key=True),
    Column("type", String),
    Column("classroom_id", BigInteger, nullable=True),
    Column("group_id", BigInteger, nullable=True),
    Column("user_a_id", BigInteger, nullable=True),
    Column("user_b_id", BigInteger, nullable=True),
    extend_existing=True,
)

classrooms_classroommembership = Table(
    "classrooms_classroommembership",
    Base.metadata,
    Column("id", BigInteger, primary_key=True),
    Column("user_id", BigInteger),
    Column("classroom_id", BigInteger),
    Column("role_in_classroom", String),
    Column("status", String),
    extend_existing=True,
)

groups_groupmembership = Table(
    "groups_groupmembership",
    Base.metadata,
    Column("id", BigInteger, primary_key=True),
    Column("user_id", BigInteger),
    Column("group_id", BigInteger),
    Column("status", String),
    extend_existing=True,
)


async def is_authorized_for_conversation(user_id: int, conversation_id: int) -> bool:
    """
    Checks if user_id is authorized to view and participate in conversation_id:
    - If DIRECT: user_id is user_a_id or user_b_id.
    - If CLASSROOM: user_id has an 'ACTIVE' row in classrooms_classroommembership for classroom_id.
    - If GROUP: user_id has an 'ACTIVE' row in groups_groupmembership for group_id.
    """
    user_id_int = int(user_id)
    conversation_id_int = int(conversation_id)

    async with async_session_maker() as session:
        # 1. Fetch conversation
        conv_stmt = select(
            conversations_conversation.c.type,
            conversations_conversation.c.classroom_id,
            conversations_conversation.c.group_id,
            conversations_conversation.c.user_a_id,
            conversations_conversation.c.user_b_id,
        ).where(conversations_conversation.c.id == conversation_id_int)

        result = await session.execute(conv_stmt)
        conv = result.first()
        if not conv:
            logger.warning(f"Conversation {conversation_id_int} not found.")
            return False

        conv_type = conv.type

        # 2. Check DIRECT
        if conv_type == "DIRECT":
            return user_id_int in (conv.user_a_id, conv.user_b_id)

        # 3. Check CLASSROOM
        elif conv_type == "CLASSROOM":
            if not conv.classroom_id:
                return False
            stmt = select(classrooms_classroommembership.c.id).where(
                classrooms_classroommembership.c.user_id == user_id_int,
                classrooms_classroommembership.c.classroom_id == conv.classroom_id,
                classrooms_classroommembership.c.status == "ACTIVE",
            )
            membership = await session.execute(stmt)
            return membership.first() is not None

        # 4. Check GROUP
        elif conv_type == "GROUP":
            if not conv.group_id:
                return False
            stmt = select(groups_groupmembership.c.id).where(
                groups_groupmembership.c.user_id == user_id_int,
                groups_groupmembership.c.group_id == conv.group_id,
                groups_groupmembership.c.status == "ACTIVE",
            )
            membership = await session.execute(stmt)
            return membership.first() is not None

        return False
