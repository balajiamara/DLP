"""
Supervised Live Verification for Step 37: MCP Server — Resources

Executes a live end-to-end verification against a running FastAPI server:
1. Starts FastAPI with MCP server mounted at /mcp.
2. Authenticates as real student (User 3) and teacher (User 2).
3. Connects a real MCP SSE client over HTTP/SSE.
4. Queries all 4 MCP resources:
   - classroom://1/overview
   - classroom://1/syllabus
   - classroom://1/progress
   - classroom://1/history
5. Queries teacher-scoped student progress:
   - classroom://1/students/3/progress
6. Verifies disconnect cleanup of session_user_map.
"""

import os
import sys
import time
import json
import asyncio
import jwt
import uvicorn
from fastapi import FastAPI
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession
from mcp.shared.exceptions import MCPError

from app.core.config import settings
from app.main import app
from app.mcp.auth import session_user_map


async def run_live_verification():
    print("==========================================================================")
    print("        SUPERVISED LIVE VERIFICATION: STEP 37 MCP SERVER RESOURCES        ")
    print("==========================================================================\n")

    port = 8011
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())

    await asyncio.sleep(1.2)

    # 1. Generate real JWT access tokens
    student_token = jwt.encode(
        {"user_id": 3, "token_type": "access", "exp": int(time.time()) + 3600},
        settings.JWT_SIGNING_KEY,
        algorithm="HS256"
    )
    teacher_token = jwt.encode(
        {"user_id": 2, "token_type": "access", "exp": int(time.time()) + 3600},
        settings.JWT_SIGNING_KEY,
        algorithm="HS256"
    )
    print("1. Generated valid JWT access tokens for Student (ID: 3) and Teacher (ID: 2).")

    try:
        # --- Part A: Student Session via Authorization Header ---
        print("\n2. Connecting real MCP client over SSE with Student Authorization header...")
        student_headers = {"Authorization": f"Bearer {student_token}"}
        sse_url = f"http://127.0.0.1:{port}/mcp/sse"

        async with sse_client(sse_url, headers=student_headers) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                print("   MCP ClientSession successfully initialized over HTTP/SSE!\n")

                # Resource 1: Classroom Overview
                print("--- [RESOURCE 1] classroom://1/overview ---")
                res_overview = await session.read_resource("classroom://1/overview")
                overview_data = json.loads(res_overview.contents[0].text)
                print(f"   Classroom Name:  {overview_data.get('name')}")
                print(f"   Teacher:         {overview_data.get('teacher', {}).get('username')} ({overview_data.get('teacher', {}).get('email')})")
                print(f"   Active Students: {overview_data.get('student_count')}")
                assert overview_data["id"] == 1
                assert overview_data["name"] == "Maths"
                assert overview_data["teacher"]["id"] == 2
                print("   [PASS] Classroom overview verified.\n")

                # Resource 2: Classroom Syllabus
                print("--- [RESOURCE 2] classroom://1/syllabus ---")
                res_syllabus = await session.read_resource("classroom://1/syllabus")
                syllabus_data = json.loads(res_syllabus.contents[0].text)
                courses = syllabus_data.get("courses", [])
                print(f"   Total Courses in Syllabus: {len(courses)}")
                for c in courses[:2]:
                    print(f"     Course: '{c.get('title')}' with {len(c.get('modules', []))} modules")
                assert len(courses) > 0
                print("   [PASS] Hierarchical syllabus verified.\n")

                # Resource 3: Student Progress (Own)
                print("--- [RESOURCE 3] classroom://1/progress ---")
                res_prog = await session.read_resource("classroom://1/progress")
                prog_data = json.loads(res_prog.contents[0].text)
                stats = prog_data.get("summary_stats", {})
                print(f"   Student ID:            {prog_data.get('student_id')}")
                print(f"   Total Topics:          {stats.get('total_topics')}")
                print(f"   Completed Topics:      {stats.get('completed_topics')}")
                print(f"   Completion Percentage: {stats.get('completion_percentage')}%")
                assert prog_data["student_id"] == 3
                assert prog_data["classroom_id"] == 1
                print("   [PASS] Student progress verified.\n")

                # Resource 4: Learning History (Own)
                print("--- [RESOURCE 4] classroom://1/history ---")
                res_history = await session.read_resource("classroom://1/history")
                history_data = json.loads(res_history.contents[0].text)
                timeline = history_data.get("timeline", [])
                print(f"   Student ID:        {history_data.get('student_id')}")
                print(f"   Total Activities:  {history_data.get('total_activities')}")
                if timeline:
                    print(f"   Latest Activity:   {timeline[0].get('type')} at {timeline[0].get('timestamp')}")
                assert history_data["student_id"] == 3
                print("   [PASS] Learning history timeline verified.\n")

        # --- Part B: Teacher Querying Student Progress & Fallback Session Map ---
        print("\n3. Testing Teacher Access & Session Map Fallback (?token=<jwt> on SSE)...")
        sse_fallback_url = f"http://127.0.0.1:{port}/mcp/sse?token={teacher_token}"

        async with sse_client(sse_fallback_url) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                print("   Teacher MCP ClientSession initialized via query token!\n")

                # Teacher querying student 3's progress
                print("--- [TEACHER SCOPED] classroom://1/students/3/progress ---")
                res_teacher_view = await session.read_resource("classroom://1/students/3/progress")
                teacher_view_data = json.loads(res_teacher_view.contents[0].text)
                print(f"   Teacher verified student progress for Student ID: {teacher_view_data.get('student_id')}")
                assert teacher_view_data["student_id"] == 3
                print("   [PASS] Teacher student progress query verified.\n")

        # --- Part C: Verify Session Cleanup ---
        print("4. Verifying session_user_map cleanup on client disconnect...")
        await asyncio.sleep(0.5)
        print(f"   Active sessions in map: {len(session_user_map)} ({session_user_map})")
        assert len(session_user_map) == 0
        print("   [PASS] session_user_map is completely clean after client disconnects.\n")

    finally:
        print("Stopping uvicorn test server...")
        server.should_exit = True
        await server_task

    print("==========================================================================")
    print("      ALL SUPERVISED LIVE MCP RESOURCE VERIFICATIONS PASSED CLEANLY!     ")
    print("==========================================================================")


if __name__ == "__main__":
    asyncio.run(run_live_verification())
