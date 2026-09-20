"""
Supervised Live Verification for Step 38: MCP Server — Tools

Executes a live end-to-end verification against a running FastAPI server:
1. Starts FastAPI with MCP server mounted at /mcp on port 8016.
2. Generates real JWT access tokens for Student (User 3) and Teacher (User 2).
3. Connects a real MCP client via HTTP/SSE.
4. Invokes all 5 MCP tools:
   - get_student_progress: Student learning progress and completion metrics.
   - get_pending_tasks: Unsubmitted assignments and unattempted quizzes.
   - search_course_material: Step 33 RAG vector search retrieval across classroom materials.
   - get_weak_topics: Detection of topics requiring review (<70% or REVIEW_REQUIRED).
   - recommend_next_topic: Explainable study recommendations with explicit reasoning text.
5. Tests Teacher cross-student querying and unauthorized access rejection.
"""

import os
import sys
import time
import json
import asyncio
import jwt
import uvicorn
from sqlalchemy import text
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

from app.core.config import settings
from app.main import app
from app.db.session import async_session_maker


async def run_live_tools_verification():
    print("==========================================================================")
    print("          SUPERVISED LIVE VERIFICATION: STEP 38 MCP SERVER TOOLS          ")
    print("==========================================================================\n")

    port = 8016
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())

    await asyncio.sleep(1.2)

    # 1. Generate real JWT access tokens
    student_token = jwt.encode(
        {"user_id": 3, "token_type": "access", "exp": int(time.time()) + 3600},
        settings.JWT_SIGNING_KEY,
        algorithm="HS256",
    )
    teacher_token = jwt.encode(
        {"user_id": 2, "token_type": "access", "exp": int(time.time()) + 3600},
        settings.JWT_SIGNING_KEY,
        algorithm="HS256",
    )
    print("1. Generated valid JWT access tokens for Student (ID: 3) and Teacher (ID: 2).")

    try:
        student_headers = {"Authorization": f"Bearer {student_token}"}
        sse_url = f"http://127.0.0.1:{port}/mcp/sse"

        print(f"\n2. Connecting real MCP client over SSE ({sse_url})...")
        async with sse_client(sse_url, headers=student_headers) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                print("   [SUCCESS] MCP ClientSession initialized over HTTP/SSE!\n")

                # List tools to confirm registration
                tools_result = await session.list_tools()
                tool_names = [t.name for t in tools_result.tools]
                print(f"   Registered MCP Tools ({len(tool_names)}): {tool_names}")
                assert "get_student_progress" in tool_names
                assert "get_pending_tasks" in tool_names
                assert "search_course_material" in tool_names
                assert "get_weak_topics" in tool_names
                assert "recommend_next_topic" in tool_names
                print("   [PASS] All 5 tools discovered in MCP tool list.\n")

                # --- TOOL 1: get_student_progress ---
                print("--- [TOOL 1] get_student_progress (Classroom 1) ---")
                res_prog = await session.call_tool("get_student_progress", {"classroom_id": 1})
                assert res_prog.is_error is False
                prog_data = json.loads(res_prog.content[0].text)
                print(f"   Student ID:            {prog_data.get('student_id')}")
                print(f"   Classroom ID:          {prog_data.get('classroom_id')}")
                print(f"   Completed Topics:      {prog_data.get('summary_stats', {}).get('completed_topics')}")
                print(f"   Completion Percentage: {prog_data.get('summary_stats', {}).get('completion_percentage')}%")
                assert prog_data["student_id"] == 3
                assert prog_data["classroom_id"] == 1
                print("   [PASS] Tool 1 get_student_progress verified.\n")

                # --- TOOL 2: get_pending_tasks ---
                print("--- [TOOL 2] get_pending_tasks (Classroom 2 with real assignments/quizzes) ---")
                res_tasks = await session.call_tool("get_pending_tasks", {"classroom_id": 2})
                assert res_tasks.is_error is False
                tasks_data = json.loads(res_tasks.content[0].text)
                print(f"   Student ID:             {tasks_data.get('student_id')}")
                print(f"   Classroom ID:           {tasks_data.get('classroom_id')}")
                print(f"   Total Pending Tasks:    {tasks_data.get('total_pending_tasks')}")
                print(f"   Pending Assignments:    {len(tasks_data.get('pending_assignments', []))}")
                for a in tasks_data.get('pending_assignments', [])[:2]:
                    print(f"     - Assignment '{a.get('title')}' (due: {a.get('due_date')}, overdue: {a.get('is_overdue')})")
                print(f"   Pending Quizzes:        {len(tasks_data.get('pending_quizzes', []))}")
                for q in tasks_data.get('pending_quizzes', [])[:2]:
                    print(f"     - Quiz '{q.get('title')}' (topic: {q.get('topic_title')})")
                assert tasks_data["student_id"] == 3
                assert tasks_data["classroom_id"] == 2
                print("   [PASS] Tool 2 get_pending_tasks verified.\n")

                # --- TOOL 3: search_course_material ---
                print("--- [TOOL 3] search_course_material (Classroom 1) ---")
                res_search = await session.call_tool("search_course_material", {
                    "classroom_id": 1,
                    "query": "geometric progressions"
                })
                assert res_search.is_error is False
                search_data = json.loads(res_search.content[0].text)
                print(f"   Classroom ID:    {search_data.get('classroom_id')}")
                print(f"   Query:           '{search_data.get('query')}'")
                print(f"   Results Found:   {search_data.get('total_results')}")
                assert search_data["classroom_id"] == 1
                assert search_data["query"] == "geometric progressions"
                print("   [PASS] Tool 3 search_course_material verified.\n")

                # --- TOOL 4: get_weak_topics ---
                print("--- [TOOL 4] get_weak_topics (Classroom 1) ---")
                res_weak = await session.call_tool("get_weak_topics", {"classroom_id": 1})
                assert res_weak.is_error is False
                weak_data = json.loads(res_weak.content[0].text)
                print(f"   Student ID:         {weak_data.get('student_id')}")
                print(f"   Mastery Threshold:  {weak_data.get('threshold')}%")
                print(f"   Total Weak Topics:  {weak_data.get('total_weak_topics')}")
                for wt in weak_data.get('weak_topics', []):
                    print(f"     - {wt.get('topic_title')}: {wt.get('reason')}")
                assert weak_data["student_id"] == 3
                assert weak_data["threshold"] == 70
                print("   [PASS] Tool 4 get_weak_topics verified.\n")

                # --- TOOL 5: recommend_next_topic ---
                print("--- [TOOL 5] recommend_next_topic (Classroom 1) ---")
                res_rec = await session.call_tool("recommend_next_topic", {"classroom_id": 1})
                assert res_rec.is_error is False
                rec_data = json.loads(res_rec.content[0].text)
                print(f"   Student ID:         {rec_data.get('student_id')}")
                print(f"   Recommended Topic:  {rec_data.get('recommended_topic')}")
                print(f"   Reason:             '{rec_data.get('reason')}'")
                assert rec_data["student_id"] == 3
                assert rec_data.get("reason") is not None
                print("   [PASS] Tool 5 recommend_next_topic verified.\n")

                # --- PART B: Cross-Student Privacy (Student 3 -> Student 4) ---
                print("--- [SECURITY] Cross-Student Privacy Enforcement ---")
                res_cross = await session.call_tool("get_student_progress", {
                    "classroom_id": 1,
                    "target_user_id": 4
                })
                print(f"   res_cross is_error: {res_cross.is_error}")
                print(f"   res_cross message:  '{res_cross.content[0].text}'")
                assert res_cross.is_error is True
                assert "Access denied" in res_cross.content[0].text
                print("   [PASS] Cross-student access cleanly rejected with non-leaking ToolError.\n")

        # --- PART C: Teacher Cross-Student Access ---
        print("\n3. Testing Teacher Access over SSE with Teacher JWT...")
        teacher_headers = {"Authorization": f"Bearer {teacher_token}"}
        async with sse_client(sse_url, headers=teacher_headers) as (t_read, t_write):
            async with ClientSession(t_read, t_write) as t_session:
                await t_session.initialize()
                print("   Teacher MCP session connected successfully.")

                # Teacher querying student 3's weak topics
                res_t_weak = await t_session.call_tool("get_weak_topics", {
                    "classroom_id": 1,
                    "target_user_id": 3
                })
                assert res_t_weak.is_error is False
                t_weak_data = json.loads(res_t_weak.content[0].text)
                print(f"   Teacher successfully queried weak topics for Student {t_weak_data.get('student_id')}!")
                assert t_weak_data["student_id"] == 3
                print("   [PASS] Teacher cross-student querying verified.\n")

    finally:
        print("Stopping uvicorn test server...")
        server.should_exit = True
        await server_task

    print("==========================================================================")
    print("        ALL SUPERVISED LIVE MCP TOOL VERIFICATIONS PASSED CLEANLY!        ")
    print("==========================================================================")


if __name__ == "__main__":
    asyncio.run(run_live_tools_verification())
