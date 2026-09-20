"""
Supervised Live End-to-End Test Script for Step 32 Document Processing Pipeline
"""

import sys
import os
import asyncio
import httpx
from fpdf import FPDF
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Import FastAPI app & services
sys.path.insert(0, os.path.abspath("."))
from app.core.config import settings
from app.services.document_processor import process_material, get_material_status_record


async def main():
    print("=== STARTING SUPERVISED LIVE END-TO-END PIPELINE TEST ===")
    print(f"Supabase URL: {settings.SUPABASE_URL}")
    print(f"Embedding Model: text-embedding-004 (Google Gemini)")

    # 1. Create a real 2-page text PDF using FPDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", size=12)
    pdf.cell(text="Daily Learning Planner - Live E2E Document Pipeline Test.")
    pdf.ln(10)
    pdf.multi_cell(
        w=0,
        h=8,
        text=(
            "This is a real text-based sample document used to perform a supervised live end-to-end "
            "verification of the Step 32 document processing pipeline. The pipeline extracts text, "
            "chunks it into sliding windows, generates 768-dimensional embeddings via Google Gemini's "
            "text-embedding-004 model, and stores the vectors in pgvector."
        ),
    )
    pdf.add_page()
    pdf.multi_cell(
        w=0,
        h=8,
        text=(
            "Section 2: Educational Technology and Artificial Intelligence Integration. "
            "The DLP microservice relies on FastAPI and asynchronous SQLAlchemy Core queries "
            "to bridge Django-managed classroom syllabi with pgvector similarity search."
        ),
    )

    pdf_bytes = bytes(pdf.output())
    file_size = len(pdf_bytes)
    storage_filename = "materials/live_e2e_test_sample.pdf"
    print(f"Generated test PDF fixture ({file_size} bytes, 2 pages).")

    # 2. Upload test PDF to Supabase Storage bucket 'materials'
    upload_url = f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/object/materials/{storage_filename.lstrip('/')}"
    headers = {
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
        "apiKey": settings.SUPABASE_SERVICE_ROLE_KEY,
        "Content-Type": "application/pdf",
        "x-upsert": "true",
    }

    async with httpx.AsyncClient() as http_client:
        upload_res = await http_client.post(upload_url, content=pdf_bytes, headers=headers)
        if upload_res.status_code not in (200, 201):
            print(f"ERROR uploading to Supabase Storage: {upload_res.status_code} - {upload_res.text}")
            return
        print(f"Successfully uploaded file to Supabase Storage path: '{storage_filename}'")

    # 3. Connect to DB and set up Django hierarchy (Classroom -> Course -> Module -> Topic -> Material)
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Check or get user ID from Django's accounts_user table
        user_res = await session.execute(text("SELECT id FROM accounts_user LIMIT 1;"))
        user_row = user_res.first()
        if not user_row:
            # Create a test user if accounts_user is empty
            user_insert = await session.execute(
                text(
                    "INSERT INTO accounts_user (password, is_superuser, email, role, is_staff, is_active, date_joined) "
                    "VALUES ('pbkdf2_sha256$test', false, 'live_test_user@example.com', 'STUDENT', false, true, NOW()) "
                    "RETURNING id;"
                )
            )
            user_id = user_insert.scalar()
        else:
            user_id = user_row[0]

        # Insert Classroom
        class_res = await session.execute(
            text(
                "INSERT INTO classrooms_classroom (name, description, teacher_id, created_at, updated_at) "
                "VALUES ('E2E Live Test Classroom', 'Classroom for live E2E pipeline test', :user_id, NOW(), NOW()) "
                "RETURNING id;"
            ),
            {"user_id": user_id},
        )
        classroom_id = class_res.scalar()

        # Insert Course
        course_res = await session.execute(
            text(
                "INSERT INTO syllabus_course (title, description, \"order\", created_at, classroom_id) "
                "VALUES ('E2E Live Test Course', 'Course for live test', 1, NOW(), :classroom_id) "
                "RETURNING id;"
            ),
            {"classroom_id": classroom_id},
        )
        course_id = course_res.scalar()

        # Insert Module
        module_res = await session.execute(
            text(
                "INSERT INTO syllabus_module (title, description, \"order\", created_at, course_id) "
                "VALUES ('E2E Live Test Module', 'Module for live test', 1, NOW(), :course_id) "
                "RETURNING id;"
            ),
            {"course_id": course_id},
        )
        module_id = module_res.scalar()

        # Insert Topic
        topic_res = await session.execute(
            text(
                "INSERT INTO syllabus_topic (title, description, \"order\", created_at, module_id) "
                "VALUES ('E2E Live Test Topic', 'Topic for live test', 1, NOW(), :module_id) "
                "RETURNING id;"
            ),
            {"module_id": module_id},
        )
        topic_id = topic_res.scalar()

        # Insert Material with status 'UPLOADED'
        mat_res = await session.execute(
            text(
                "INSERT INTO syllabus_material (title, file_name, storage_path, file_type, file_size_bytes, status, failure_reason, created_at, topic_id, uploaded_by_id) "
                "VALUES ('Live E2E Document', 'live_e2e_test_sample.pdf', :storage_path, 'pdf', :file_size, 'UPLOADED', NULL, NOW(), :topic_id, :user_id) "
                "RETURNING id;"
            ),
            {
                "storage_path": storage_filename,
                "file_size": file_size,
                "topic_id": topic_id,
                "user_id": user_id,
            },
        )
        material_id = mat_res.scalar()
        await session.commit()

        print(
            f"Created DB Hierarchy -> Classroom: {classroom_id}, Course: {course_id}, Module: {module_id}, Topic: {topic_id}, Material: {material_id}"
        )

    # 4. Trigger full document processing pipeline
    print(f"\n--- Triggering process_material({material_id}) with REAL Gemini API API key ---")
    await process_material(material_id)

    # 5. Check status and results
    status_record = await get_material_status_record(material_id)
    print(f"Material Final Status: {status_record['status']}")

    if status_record["status"] == "FAILED":
        print(f"FAILURE REASON: {status_record['failure_reason']}")
    elif status_record["status"] == "READY":
        async with async_session() as session:
            emb_res = await session.execute(
                text(
                    "SELECT id, material_id, topic_id, classroom_id, chunk_index, chunk_text, vector_dims(embedding) as dim, embedding "
                    "FROM embeddings WHERE material_id = :material_id ORDER BY chunk_index;"
                ),
                {"material_id": material_id},
            )
            rows = emb_res.all()
            print(f"\nSUCCESS: Embedded {len(rows)} text chunk(s) into pgvector embeddings table.")
            for row in rows:
                id_, mat_id, top_id, class_id, idx, chunk_text_str, dims, vec_str = row
                vec_sample = str(vec_str)[:60] + "..."
                print(f"\n[Chunk {idx}]")
                print(f"  Classroom ID: {class_id}, Topic ID: {top_id}")
                print(f"  Chunk Index: {idx}")
                print(f"  Chunk Text: '{chunk_text_str[:120]}...'")
                print(f"  Vector Dimension: {dims} (Expected: 768)")
                print(f"  Vector Sample values: {vec_sample}")

    await engine.dispose()
    print("\n=== LIVE TEST COMPLETE ===")


if __name__ == "__main__":
    asyncio.run(main())
