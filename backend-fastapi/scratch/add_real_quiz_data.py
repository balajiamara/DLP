import asyncio
from sqlalchemy import text
from app.db.session import async_session_maker

async def add_quiz():
    async with async_session_maker() as s:
        q = (await s.execute(text("SELECT id FROM assessments_quiz WHERE topic_id=1"))).first()
        if not q:
            res = await s.execute(text("""
                INSERT INTO assessments_quiz (classroom_id, topic_id, title, created_by_id, created_at)
                VALUES (1, 1, 'Arithmetic Quiz 1', 2, NOW())
                RETURNING id
            """))
            quiz_id = res.scalar()
            await s.commit()
            print("Created Quiz ID:", quiz_id)
        else:
            quiz_id = q[0]
            print("Existing Quiz ID:", quiz_id)

        att = (await s.execute(text("SELECT id, score FROM assessments_quizattempt WHERE quiz_id=:qid AND student_id=3"), {"qid": quiz_id})).first()
        if not att:
            await s.execute(text("""
                INSERT INTO assessments_quizattempt (quiz_id, student_id, answers, score, attempted_at)
                VALUES (:qid, 3, '{"1": "A"}', 60, NOW())
            """), {"qid": quiz_id})
            await s.commit()
            print("Created Quiz Attempt with score 60% (below 70% threshold)")
        else:
            print("Existing Quiz Attempt:", att)

if __name__ == "__main__":
    asyncio.run(add_quiz())
