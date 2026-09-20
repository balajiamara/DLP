import asyncio
from sqlalchemy import text
from app.db.session import async_session_maker

async def check():
    async with async_session_maker() as session:
        courses = (await session.execute(
            text("SELECT id, title, description, \"order\" FROM syllabus_course WHERE classroom_id = :cid ORDER BY \"order\", id"),
            {"cid": 1}
        )).mappings().all()
        print("Courses:", [dict(c) for c in courses])

        modules = (await session.execute(
            text("SELECT id, course_id, title, description, \"order\" FROM syllabus_module ORDER BY \"order\", id")
        )).mappings().all()
        print("Modules count:", len(modules))

        topics = (await session.execute(
            text("SELECT id, module_id, title, description, \"order\" FROM syllabus_topic ORDER BY \"order\", id")
        )).mappings().all()
        print("Topics count:", len(topics))

        progress = (await session.execute(
            text("SELECT id, topic_id, student_id, learning_state, updated_at FROM syllabus_topicprogress")
        )).mappings().all()
        print("Topic progress count:", len(progress))

        quizzes = (await session.execute(
            text("SELECT id, quiz_id, student_id, score, attempted_at FROM assessments_quizattempt")
        )).mappings().all()
        print("Quiz attempts count:", len(quizzes))

        submissions = (await session.execute(
            text("SELECT id, assignment_id, student_id, grade, submitted_at FROM assessments_submission")
        )).mappings().all()
        print("Submissions count:", len(submissions))

        doubts = (await session.execute(
            text("SELECT id, classroom_id, author_id, title, created_at FROM doubts_doubt")
        )).mappings().all()
        print("Doubts count:", len(doubts))

        replies = (await session.execute(
            text("SELECT id, doubt_id, author_id, is_accepted_answer, created_at FROM doubts_doubtreply")
        )).mappings().all()
        print("Replies count:", len(replies))

if __name__ == "__main__":
    asyncio.run(check())
