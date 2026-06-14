# XENO CRM — AI-Native Mini CRM for Reaching Shoppers

> An intelligent, chat-first customer engagement platform built for **BeanBox Coffee** — a premium coffee chain brand. Marketers describe what they want in natural language, and the AI agent handles segmentation, message drafting, and omnichannel campaign execution.

**Live Demo:** [https://frontend-ten-beige-70.vercel.app](https://frontend-ten-beige-70.vercel.app)

---

## Architecture

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────────┐
│   Next.js        │────▶│   FastAPI         │────▶│  Channel Service     │
│   Frontend       │     │   Backend         │     │  (Stub)              │
│   (Vercel)       │◀────│   (Render/Koyeb)  │◀────│  (Render)            │
│                  │     │                   │     │                      │
│ • Dashboard      │     │ • REST API        │     │ • Simulates delivery │
│ • AI Chat        │     │ • AI Agent (Groq) │     │ • Async callbacks    │
│ • Customers      │     │ • Segmentation    │     │ • Engagement funnel: │
│ • Segments       │     │ • Campaign Engine │     │   delivered → opened │
│ • Campaigns      │     │ • Receipt Handler │     │   → read → clicked  │
│ • Data Import    │     │ • Data Ingestion  │     │   → converted       │
└──────────────────┘     └──────────────────┘     └──────────────────────┘
                                │
                         ┌──────┴──────┐
                         │ PostgreSQL  │
                         │ (Supabase)  │
                         └─────────────┘
```

### Three-Service Design

| Service | Tech | Purpose |
|---------|------|---------|
| **Frontend** | Next.js 16, React 19, Vanilla CSS | Glassmorphism dark-mode UI with chat-first experience |
| **Backend** | FastAPI, SQLAlchemy (async), PostgreSQL | REST API, AI agent orchestration, campaign engine |
| **Channel Service** | FastAPI (separate service) | Stubbed channel delivery simulator with async receipt callbacks |

### The Callback Loop (Key Design Decision)

The CRM and Channel Service communicate via a **two-service, callback-driven loop**:

1. **CRM → Channel Service:** When a campaign is sent, the CRM calls `/channel/send` with a batch of communications and a `callback_url`
2. **Channel Service → CRM:** The channel service responds immediately (`202 Accepted`) and asynchronously simulates the delivery lifecycle in the background
3. **Async Receipts:** At each stage (delivered → opened → read → clicked → converted), the channel service POSTs batched `DeliveryReceipt` callbacks to the CRM's `/api/receipts/batch` endpoint
4. **CRM Updates:** The receipt handler updates individual `Communication` records and increments campaign-level aggregate counters, with **idempotency guards** to prevent status regression

---

## AI-Native Design

The product uses a **chat-first, AI-agent architecture** where the AI isn't bolted on — it's the primary interface:

### AI Agent Capabilities (Tool Calling)

The agent uses **Groq (Llama 3.3 70B)** as primary LLM with **Gemini 2.5 Flash** as fallback, and has access to these tools:

| Tool | What it does |
|------|-------------|
| `query_customers` | Queries customer data with structured filters |
| `create_segment` | Creates audience segments from rules |
| `draft_message` | Generates personalized marketing messages |
| `create_campaign` | Creates campaign drafts targeting segments |
| `send_campaign` | Dispatches campaigns to the channel service |
| `get_campaign_stats` | Retrieves delivery/engagement funnel metrics |
| `get_insights` | Surfaces business intelligence and suggestions |

### Example Flow
```
User: "Find customers who spent more than ₹5000 and send them a WhatsApp 
       campaign with a 20% discount on cold brew"

AI:   1. Calls query_customers(filters=[{field: "total_spend", operator: ">", value: 5000}])
      2. Calls create_segment(name="High-Value Customers", rules=[...])
      3. Calls draft_message(segment_description="high spenders", channel="whatsapp", offer="20% off cold brew")
      4. Calls create_campaign(name="Cold Brew VIP Offer", segment_id="...", message_template="...", channel="whatsapp")
      5. Calls send_campaign(campaign_id="...")
      → Campaign dispatched. Delivery receipts arrive asynchronously.
```

---

## Data Model

| Table | Purpose |
|-------|---------|
| `customers` | Shopper profiles with spend aggregates, order counts, tags |
| `orders` | Purchase history linked to customers (JSONB items) |
| `segments` | Rule-based audience definitions (AI-generated or manual) |
| `segment_members` | Materialized segment membership (many-to-many) |
| `campaigns` | Campaign metadata + aggregate delivery/engagement counters |
| `communications` | Per-recipient delivery tracking with full status lifecycle |
| `ai_conversations` | Chat history with context for multi-turn conversations |

### Communication Status Lifecycle
```
queued → delivered → opened → read → clicked → converted
              ↘ failed
```

The `converted` status tracks **order attribution** — when a customer places an order as a result of receiving a communication.

---

## Tech Stack

- **Frontend:** Next.js 16 (App Router), React 19, Vanilla CSS (custom glassmorphism dark theme)
- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0 (async), asyncpg
- **Database:** PostgreSQL (Supabase)
- **AI:** Groq (Llama 3.3 70B) primary, Google Gemini 2.5 Flash fallback
- **HTTP:** httpx (async) for inter-service communication
- **Deployment:** Vercel (frontend), Render (backend + channel service)

---

## Local Development Setup

### Prerequisites
- Python 3.12
- Node.js 18+
- PostgreSQL database (or Supabase account)

### 1. Clone & Configure

```bash
git clone https://github.com/YOUR_USERNAME/xeno-crm.git
cd xeno-crm

# Backend environment
cp backend/.env.example backend/.env
# Edit backend/.env with your DATABASE_URL, GROQ_API_KEY, GEMINI_API_KEY

# Channel service environment
cp channel-service/.env.example channel-service/.env
```

### 2. Database Setup

Run `backend/schema.sql` against your PostgreSQL database:
```bash
psql $DATABASE_URL -f backend/schema.sql
```

### 3. Start All Services

```powershell
# Windows (PowerShell)
./start.ps1
```

Or manually:
```bash
# Terminal 1: Channel Service
cd channel-service
pip install -r requirements.txt
uvicorn app.main:app --port 8001

# Terminal 2: Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --port 8000

# Terminal 3: Frontend
cd frontend
npm install
npm run dev
```

### 4. Seed Data

```bash
cd seed
python ingest.py
```

Or use the **Data Import** page in the UI to load demo data with one click.

---

## Deployment

For a step-by-step deployment checklist, hosted env var map, seed instructions, and smoke tests, see `DEPLOYMENT.md`.

### Frontend → Vercel
```bash
cd frontend
npx vercel --prod
```
Set `NEXT_PUBLIC_API_URL` environment variable to your backend URL.

### Backend + Channel Service → Render
Use the `render.yaml` blueprint or deploy each Dockerfile individually. Required env vars:
- `DATABASE_URL` — PostgreSQL connection string
- `GROQ_API_KEY` — Groq API key
- `GEMINI_API_KEY` — Google Gemini API key
- `CHANNEL_SERVICE_URL` — URL of the channel service
- `FRONTEND_URL` — URL of the frontend (for CORS)
- `BACKEND_URL` — Self URL (for channel service callbacks)

---

## Key Design Decisions

1. **Chat-first, not form-first:** The primary UX is conversational. Traditional CRUD views exist as read-only dashboards, not the primary workflow.

2. **Materialized segments:** Segment membership is pre-computed and stored in `segment_members`, enabling fast campaign dispatch without re-evaluating rules at send time.

3. **Bulk ingestion with dialect awareness:** Customer/order ingestion uses database-specific upsert primitives for PostgreSQL and SQLite, while aggregate recalculation uses portable SQLAlchemy so the local demo and production database behave consistently.

4. **Idempotent receipt processing:** The receipt handler accepts only forward lifecycle transitions, blocks late failures after delivery/engagement, and updates campaign counters from accepted communication state transitions so duplicate callbacks do not inflate metrics.

5. **Dual-LLM fallback:** Groq is blazing fast but rate-limited. Gemini 2.5 Flash provides a seamless fallback so the AI never goes down.

6. **Conversion attribution:** The channel service simulates order conversions (20% of clickers), and the CRM tracks this as a first-class status in the delivery funnel.

7. **Scoped retry instead of fake infrastructure:** The channel stub uses bounded in-process callback retries with backoff. At production scale this would move to a durable queue/outbox with idempotency keys, replay tooling, and dead-letter handling.

---

## Scale Assumptions and Tradeoffs

- Demo dataset: roughly 5,000 customers and realistic purchase history, enough to show segmentation and campaign fanout without overbuilding distributed infrastructure.
- Campaign size: thousands of recipients per campaign, not millions. A single application instance is acceptable for the take-home demo.
- Segment membership is materialized because campaign dispatch should not re-evaluate rules for every send.
- Communications are inserted before channel dispatch so every recipient has an auditable row. If the channel service is unreachable, the campaign is marked `failed` and the API returns an error instead of claiming success.
- Receipt batches preload matching communications/campaigns, apply counter deltas in memory, and flush progress every 250 accepted transitions so local SQLite demos do not stall under large callback bursts.
- Callback retry is bounded and in-process for this scope. In production, the channel service would use a durable queue, transactional outbox, idempotency keys, worker concurrency limits, observability, and a replay/dead-letter workflow.
- SQLite is supported for local demos; PostgreSQL/Supabase is the intended hosted database. Tags are stored as JSON arrays in both paths to avoid ORM/schema drift.
- The AI agent confirms before persistence-heavy actions where possible. Dashboard quick segment actions use deterministic segment APIs so the UI never pretends a preview was persisted.

## AI-Native Development Workflow

- AI was used to accelerate architecture review, identify submission-blocking risks, and draft implementation options.
- Generated ideas were inspected against the codebase before edits; fixes were kept small and tied to assignment requirements.
- AI output that needed correction included false-success campaign dispatch, overly optimistic README claims, and PostgreSQL-only SQL in a SQLite local path.
- Ownership was maintained through direct code review, focused tests, lint/build verification, and explicit tradeoff documentation.

## Verification

- Frontend lint: `npm.cmd run lint`
- Frontend production build: `npm.cmd run build`
- Python syntax check: `python -m py_compile ...`
- Backend tests: `python -m unittest discover -s backend\tests` after creating a Python 3.12 environment and installing `backend/requirements.txt`

Note: Python 3.14 is currently installed on this machine, but the backend dependency set is pinned for Python 3.12. `start.ps1` now detects a stale or missing environment and requires Python 3.12 instead of silently creating an incompatible venv.

See `WALKTHROUGH.md` for the 5-6 minute video script and demo checklist.

---

## Project Structure

```
xeno-crm/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app + CORS + lifespan
│   │   ├── config.py            # Environment configuration
│   │   ├── database.py          # SQLAlchemy async engine + session
│   │   ├── schemas.py           # Pydantic request/response models
│   │   ├── models/              # SQLAlchemy ORM models
│   │   ├── routers/             # API route handlers
│   │   │   ├── customers.py     # Customer CRUD + bulk ingest
│   │   │   ├── orders.py        # Order bulk ingest
│   │   │   ├── segments.py      # Segment CRUD + preview + refresh
│   │   │   ├── campaigns.py     # Campaign CRUD + send + stats
│   │   │   ├── receipts.py      # Delivery receipt webhook handler
│   │   │   └── ai.py            # AI chat + tool execution loop
│   │   └── services/
│   │       ├── ai_agent.py      # LLM orchestration + tool definitions
│   │       ├── campaign_engine.py # Campaign send + personalization
│   │       ├── segmentation.py  # Rule evaluation + membership
│   │       └── ingestion.py     # Bulk upsert + aggregate updates
│   ├── schema.sql               # Database DDL
│   ├── Dockerfile
│   └── requirements.txt
├── channel-service/
│   ├── app/
│   │   ├── main.py              # FastAPI endpoint for /channel/send
│   │   └── simulator.py         # Async delivery lifecycle simulation
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── app/
│       │   ├── (public)/        # Landing, login, register
│       │   └── (app)/           # Authenticated dashboard pages
│       ├── components/          # Sidebar, layout
│       └── lib/                 # API client, auth helpers
├── seed/                        # Data generation + ingestion scripts
├── render.yaml                  # Render deployment blueprint
└── start.ps1                    # Local dev startup script
```

---

Built for the Xeno FDE/SDE Take-Home Assignment.
