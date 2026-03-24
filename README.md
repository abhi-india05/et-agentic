# RevOps AI — Autonomous Sales & Revenue Intelligence System

A production-grade **multi-agent AI system** built with LangGraph + FastAPI + React that autonomously manages the full sales lifecycle.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     ORCHESTRATOR                        │
│                   (LangGraph Graph)                     │
└───┬──────────────┬──────────────┬───────────────────────┘
    │              │              │
    ▼              ▼              ▼
PROSPECTING   DEAL INTEL    CHURN PREDICT
    │              │              │
    ▼              ▼              ▼
DIGITAL TWIN  CRM AUDITOR   ACTION AGENT
    │              │              │
    ▼              ▼              ▼
  OUTREACH    ACTION AGENT  EXPLAINABILITY
    │              │              │
    └──────────────┴──────────────┘
                   │
            FAILURE RECOVERY
                   │
           EXPLAINABILITY
```

**10 Agents:**
1. `orchestrator` — LangGraph state machine routing all workflows
2. `prospecting_agent` — Identifies decision-makers, scores leads
3. `digital_twin_agent` — Simulates buyer psychology and objections
4. `outreach_agent` — Generates 3-email personalized sequences
5. `deal_intelligence_agent` — Detects inactivity, competitor signals
6. `crm_auditor_agent` — Finds missed follow-ups, stuck deals
7. `churn_agent` — Multi-factor churn scoring + retention strategies
8. `action_agent` — Sends emails, updates CRM records
9. `explainability_agent` — Generates reasoning audit trails
10. `failure_recovery` — Retry logic, fallbacks, escalation

---

## Quick Start

### 1. Clone & Setup

```bash
cd revops-ai
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

### 2. Backend

```bash
cd backend
pip install -r ../requirements.txt
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:5173
```

---

## Environment Variables

```env
OPENAI_API_KEY=sk-...          # Required — OpenAI API key (GPT-4o)
MONGODB_URI=mongodb://...      # Optional — defaults to local MongoDB
SENDGRID_API_KEY=SG....        # Optional — uses mock mode if not set
OPENAI_MODEL=gpt-4o            # Model to use
ENVIRONMENT=development        # development | production
```

> **Note:** `SENDGRID_API_KEY` is optional. Without a valid SG. key, emails are logged in mock mode — all functionality works.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/run-outreach` | Cold outreach pipeline |
| `POST` | `/detect-risk` | Deal risk detection |
| `POST` | `/predict-churn` | Churn prediction |
| `GET` | `/logs` | Audit logs |
| `GET` | `/pipeline` | CRM pipeline stats |
| `GET` | `/emails` | Email activity |
| `GET` | `/sessions` | Active sessions |
| `GET` | `/health` | System health |

### Example Requests

**Cold Outreach:**
```bash
curl -X POST http://localhost:8000/run-outreach \
  -H "Content-Type: application/json" \
  -d '{"company":"Acme Corp","industry":"SaaS","size":"51-200"}'
```

**Risk Detection:**
```bash
curl -X POST http://localhost:8000/detect-risk \
  -H "Content-Type: application/json" \
  -d '{"inactivity_threshold_days":10,"check_all":true}'
```

**Churn Prediction:**
```bash
curl -X POST http://localhost:8000/predict-churn \
  -H "Content-Type: application/json" \
  -d '{"top_n":3}'
```

---

## Agent Output Format

All agents return:
```json
{
  "status": "success | failure | escalated",
  "data": {},
  "reasoning": "Human-readable explanation",
  "confidence": 0.0,
  "agent_name": "agent_name",
  "timestamp": "ISO datetime",
  "error": null
}
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Agent Framework | LangGraph |
| LLM | OpenAI GPT-4o |
| Backend | FastAPI + Python |
| Database | MongoDB (CRM simulation) |
| Vector Memory | FAISS |
| Email | SendGrid (mock fallback) |
| Frontend | React + Vite + Tailwind |
| Charts | Recharts |
| Retries | Tenacity |
| Logging | Structlog |

---

## Project Structure

```
revops-ai/
├── backend/
│   ├── main.py                    # FastAPI app
│   ├── config/settings.py         # Environment config
│   ├── agents/
│   │   ├── orchestrator.py        # LangGraph workflows
│   │   ├── prospecting_agent.py
│   │   ├── digital_twin_agent.py
│   │   ├── outreach_agent.py
│   │   ├── deal_intelligence_agent.py
│   │   ├── crm_auditor_agent.py
│   │   ├── churn_agent.py
│   │   ├── action_agent.py
│   │   ├── explainability_agent.py
│   │   └── failure_recovery.py
│   ├── tools/
│   │   ├── crm_tool.py            # CRM operations
│   │   ├── email_tool.py          # SendGrid integration
│   │   └── scraping_tool.py       # Company enrichment
│   ├── memory/vector_store.py     # FAISS memory
│   ├── models/schemas.py          # Pydantic models
│   ├── data/
│   │   ├── sample_crm.json        # 20 account dataset
│   │   └── usage_data.json        # Usage/churn signals
│   └── utils/
│       ├── logger.py              # Structlog + audit store
│       └── helpers.py             # Utilities
└── frontend/
    └── src/
        ├── pages/                 # Route pages
        ├── components/            # Reusable UI
        └── utils/                 # API + formatting
```

---

## Key Features

- **LangGraph State Machine** — Three separate compiled graphs for each workflow type
- **10 Autonomous Agents** — Each with independent retry logic via Tenacity
- **FAISS Memory** — Persistent cross-session context for personalization
- **20-Account Dataset** — Pre-seeded CRM with realistic signals for churn/risk demos
- **Explainability Layer** — Every decision logged with reasoning and confidence
- **Failure Recovery** — Automatic retry (2x), fallback strategies, escalation flags
- **Mock Mode** — Runs without MongoDB/SendGrid for immediate testing
