import sys
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text
from app.db.session import async_session_maker


async def clean_and_show():
    async with async_session_maker() as session:
        del_res = await session.execute(
            text("DELETE FROM ai_interaction_logs WHERE query_text = :q;"),
            {"q": "Explain the fundamentals of linear algebra."}
        )
        await session.commit()
        print(f"Deleted stale test rows: {del_res.rowcount}")

        check_res = await session.execute(
            text("SELECT id, interaction_type, query_text, grounded, retrieved_chunk_count, retrieved_chunk_ids FROM ai_interaction_logs WHERE classroom_id = 6;")
        )
        rows = check_res.mappings().all()
        print(f"Remaining rows for classroom 6 ({len(rows)}):")
        for r in rows:
            print(f"- {r['id']} | {r['interaction_type']} | grounded={r['grounded']} | chunks={r['retrieved_chunk_count']} | {r['retrieved_chunk_ids']}")

if __name__ == "__main__":
    asyncio.run(clean_and_show())
