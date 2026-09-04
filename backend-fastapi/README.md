# Daily Learning Planner (DLP) — FastAPI Microservice Scaffold

FastAPI microservice built with **FastAPI**, **SQLAlchemy 2.0 (AsyncIO)**, **asyncpg**, and **pydantic-settings**.

---

## 🛠️ Local Development Setup

### 1. Create and Activate Virtual Environment
```bash
cd backend-fastapi
python -m venv venv

# Windows (PowerShell)
.\venv\Scripts\Activate.ps1

# macOS / Linux
source venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Edit `.env` and set `DATABASE_URL` to your Supabase PostgreSQL connection string (using the `postgresql+asyncpg://` driver prefix).

### 4. Run Development Server
Run Uvicorn on port **8001** (to avoid port conflicts with Django running on port 8000):
```bash
uvicorn app.main:app --reload --port 8001
```

### 5. Verify Endpoints
- Root sanity check: `http://localhost:8001/`
- Process liveness check: `http://localhost:8001/health/live`
- Database readiness check: `http://localhost:8001/health/ready`

---

## 🔗 Supabase Connection Strings: Direct (Port 5432) vs. Pooler (Port 6543)

Supabase offers two connection modes:
1. **Direct Connection (`port 5432`)** [RECOMMENDED FOR FASTAPI]:
   - Direct connection to PostgreSQL database.
   - Recommended for persistent, long-lived server processes like FastAPI deployed on Render.
2. **Transaction Pooler / PgBouncer (`port 6543`)**:
   - Connection pooler intended for serverless or edge functions (e.g. Vercel / AWS Lambda) that establish ephemeral short-lived connections.

> 💡 **Recommendation**: Use the **Direct Connection string (`port 5432`)** for this FastAPI service. Since FastAPI runs as a persistent service on Render, managing an in-app SQLAlchemy connection pool (`pool_size=5`) directly against PostgreSQL is cleaner and avoids connection pooler overhead.
>
> **Note on PgBouncer compatibility**: In `app/db/session.py`, `connect_args={"statement_cache_size": 0}` is explicitly set. This disables asyncpg's prepared statement cache so that if you ever use the PgBouncer pooler (port 6543) in transaction mode, queries will execute without prepared statement collisions.

---

## 🚀 Render Deployment Prep

To deploy this service as a web service on Render:

1. **Root Directory**: `backend-fastapi`
2. **Build Command**: `pip install -r requirements.txt`
3. **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. **Environment Variables**:
   - `DATABASE_URL`: `postgresql+asyncpg://postgres.<project_ref>:<password>@<host>:5432/postgres`
   - `ALLOWED_ORIGINS`: `https://your-frontend.vercel.app`
   - `ENVIRONMENT`: `production`
5. **Health Check Path**: `/health/live`

---

## 🧪 Testing

Run pytest test suite:
```bash
pytest
```
