## Tydline Core Backend

Tydline is an early-warning container intelligence system that helps importers
track containers and receive proactive notifications before demurrage fees occur.

This repository contains the FastAPI-based backend skeleton.

### Tech Stack

- **Language**: Python 3.11+
- **Framework**: FastAPI
- **Database**: Supabase Postgres (SQLAlchemy async, `asyncpg`)
- **Container tracking**: ShipsGo API
- **Email**: Postmark
- **AI alerts**: Groq (optional)
- **AI Agent**: Pydantic AI + Qwen 2.5 (Groq) + Mem0 for conversational logistics (optional)
- **Messaging**: WhatsApp Business API (optional)
- **HTTP Client**: httpx
- **Architecture**: service-oriented, async-first, AI-ready

### Project Layout

- `app/api` – REST API routers (e.g. `shipments.py`)
- `app/services` – business logic (tracking, notifications)
- `app/models` – SQLAlchemy ORM models and Pydantic schemas
- `app/database` – async engine and session management
- `app/workers` – background tracking workers
- `app/config` – environment-based configuration
- `app/utils` – retry helper, etc.
- `app/api/deps.py` – API key auth (optional)
- `app/services/ai_service.py` – Groq alert drafting
- `app/agent/` – Pydantic AI logistics agent (Qwen 2.5, Mem0), `POST /agent/chat`
- `app/integrations` – external system client abstractions
- `scripts` – helper scripts (cron/worker entrypoints)
- `tests` – API and service tests

### Setup (local)

1. **Install dependencies**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e .
   ```

2. **Configure environment**

   ```bash
   cp .env.example .env
   # Set: DATABASE_URL, SHIPSGO_API_KEY, POSTMARK_SERVER_TOKEN, EMAIL_FROM;
   # optional: GROQ_API_KEY, GROQ_MODEL_AGENT=qwen-2.5-32b, MEM0_API_KEY,
   # WHATSAPP_ACCESS_TOKEN, WHATSAPP_PHONE_NUMBER_ID, API_KEY
   ```

3. **Run database migrations**

   This skeleton defines models but does not include a migration tool.
   In production, configure Alembic or Supabase migrations for schema management.

4. **Run the API locally**

   ```bash
   uvicorn app.main:app --reload
   ```

5. **Run the tracker worker once (local)**

   ```bash
   python -m app.workers.tracker_worker
   ```

### MVP Behavior

- `POST /shipments/track` – store shipment, start tracking in background, return:

  ```json
  {
    "status": "tracking_started",
    "container_number": "MSCU1234567"
  }
  ```

- A periodic worker (`app/workers/tracker_worker.py`) refreshes active shipments
  via ShipsGo, compares status changes, updates the database, and triggers
  notifications via Postmark and `app/services/notification_service.py`.

### AI Agent layer (optional)

- **Pydantic AI** – Agent framework with tools and dependency injection.
- **Qwen 2.5** – Model used for the agent via Groq (`GROQ_MODEL_AGENT=qwen-2.5-32b`).
- **Mem0** – Conversation/shipment memory; set `MEM0_API_KEY` for cloud memory (otherwise agent runs without memory).

`POST /agent/chat` sends a user message and returns the agent’s reply. The agent can list the user’s shipments and fetch live container status via ShipsGo. For production WhatsApp or chat UIs, call this endpoint with the same `user_id` so Mem0 can retain context across turns.

The design keeps API, services, and persistence layers cleanly separated, and
leaves clear integration points for AI ETA prediction, WhatsApp agents, and
document ingestion pipelines.

### Serverless deployment (Google Cloud Run)

For production, the backend is deployed as fully serverless containers on
Google Cloud Run:

- `tydline-api` – FastAPI HTTP service exposing `/shipments/*` and `/health`
- `tydline-tracker` – Cloud Run Job running `python -m app.workers.tracker_worker`
  on a schedule via Cloud Scheduler (e.g. every 4 hours)

#### Build and deploy the API service

1. Build and push the container image:

   ```bash
   gcloud builds submit --tag gcr.io/PROJECT_ID/tydline-core
   ```

2. Deploy to Cloud Run:

   ```bash
   gcloud run deploy tydline-api \
     --image gcr.io/PROJECT_ID/tydline-core \
     --platform managed \
     --region REGION \
     --allow-unauthenticated \
     --set-env-vars "DATABASE_URL=...,SUPABASE_URL=...,SUPABASE_ANON_KEY=...,SHIPSGO_API_KEY=...,SHIPSGO_API_BASE_URL=...,POSTMARK_SERVER_TOKEN=...,EMAIL_FROM=...,WHATSAPP_ACCESS_TOKEN=...,WHATSAPP_PHONE_NUMBER_ID=..."
   ```

#### Create the tracker job

1. Create the Cloud Run Job:

   ```bash
   gcloud run jobs create tydline-tracker \
     --image gcr.io/PROJECT_ID/tydline-core \
     --region REGION \
     --command python --args "-m,app.workers.tracker_worker" \
     --set-env-vars "DATABASE_URL=...,SUPABASE_URL=...,SHIPSGO_API_KEY=...,SHIPSGO_API_BASE_URL=...,POSTMARK_SERVER_TOKEN=...,EMAIL_FROM=...,WHATSAPP_ACCESS_TOKEN=...,WHATSAPP_PHONE_NUMBER_ID=..."
   ```

2. Schedule it with Cloud Scheduler (every 4 hours):

   ```bash
   gcloud scheduler jobs create http tydline-tracker-schedule \
     --schedule "0 */4 * * *" \
     --uri "https://REGION-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/PROJECT_ID/jobs/tydline-tracker:run" \
     --http-method POST \
     --oauth-service-account-email YOUR_SA@PROJECT_ID.iam.gserviceaccount.com
   ```


