# 🚀 RevOps AI — Autonomous Sales & Revenue Intelligence System.
# link : https://et-agentic-manipal-super-kings.vercel.app/

A production-grade **multi-agent AI platform** that autonomously manages the full sales lifecycle — from prospecting to churn prevention.

Built using **LangGraph + FastAPI + React**, this system simulates a fully operational RevOps engine powered by intelligent agents.

---

## 🧠 Overview

RevOps AI is designed to:

-   Automate **lead generation and outreach**
    
-   Detect **deal risks in real-time**
    
-   Predict and prevent **customer churn**
    
-   Maintain **CRM hygiene automatically**
    
-   Provide **explainable AI-driven decisions**
    

---

## 🏗️ System Architecture

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

---

## 🤖 Agents

The system consists of **10 specialized AI agents**:

| Agent | Role |
| --- | --- |
| `orchestrator` | Routes workflows via LangGraph |
| `prospecting_agent` | Finds leads & scores them |
| `digital_twin_agent` | Simulates buyer psychology |
| `outreach_agent` | Generates personalized email sequences |
| `deal_intelligence_agent` | Detects deal risks & signals |
| `crm_auditor_agent` | Identifies CRM inefficiencies |
| `churn_agent` | Predicts churn & suggests retention |
| `action_agent` | Executes actions (emails, CRM updates) |
| `explainability_agent` | Generates reasoning trails |
| `failure_recovery` | Handles retries & escalation |

---

## ⚡ Quick Start

### 1\. Clone & Setup

```
Bash

cd revops-ai  
cp .env.example .env
```

Update your `.env` file with required keys.

---

### 2\. Backend

```
Bash

cd backend  
pip install \-r ../requirements.txt  
python \-m uvicorn backend.main:app \--host 0.0.0.0 \--port 8000 \--reload
```

---

### 3\. Frontend

```
Bash

cd frontend  
npm install  
npm run dev
```

👉 Open: [http://localhost:5173](http://localhost:5173)

---

## 🔐 Environment Variables

```
env

OPENAI\_API\_KEY=sk-...          # Required  
MONGODB\_URI=mongodb://...      # Optional  
SENDGRID\_API\_KEY=SG....        # Optional  
OPENAI\_MODEL=gpt-4o            # Default model  
ENVIRONMENT=development        # dev | prod
```

> 💡 If `SENDGRID_API_KEY` is not set, the system runs in **mock email mode**.

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| POST | `/run-outreach` | Run cold outreach pipeline |
| POST | `/detect-risk` | Detect deal risks |
| POST | `/predict-churn` | Predict churn |
| GET | `/logs` | View audit logs |
| GET | `/pipeline` | CRM stats |
| GET | `/emails` | Email activity |
| GET | `/sessions` | Active sessions |
| GET | `/health` | System health |

---

### 📡 Example Requests

#### Cold Outreach

```
Bash

curl \-X POST http://localhost:8000/run-outreach \\  
  \-H "Content-Type: application/json" \\  
  \-d '{"company":"Acme Corp","industry":"SaaS","size":"51-200"}'
```

#### Deal Risk Detection

```
Bash

curl \-X POST http://localhost:8000/detect-risk \\  
  \-H "Content-Type: application/json" \\  
  \-d '{"inactivity\_threshold\_days":10,"check\_all":true}'
```

#### Churn Prediction

```
Bash

curl \-X POST http://localhost:8000/predict-churn \\  
  \-H "Content-Type: application/json" \\  
  \-d '{"top\_n":3}'
```

---

## 📦 Agent Output Format

All agents return a standardized response:

```
JSON

{  
  "status": "success | failure | escalated",  
  "data": {},  
  "reasoning": "Human-readable explanation",  
  "confidence": 0.0,  
  "agent\_name": "agent\_name",  
  "timestamp": "ISO datetime",  
  "error": null  
}
```

---

## 🧰 Tech Stack

| Layer | Technology |
| --- | --- |
| Agent Framework | LangGraph |
| LLM | OpenAI GPT-4o |
| Backend | FastAPI (Python) |
| Database | MongoDB |
| Vector Memory | FAISS |
| Email | SendGrid |
| Frontend | React + Vite + Tailwind |
| Charts | Recharts |
| Retries | Tenacity |
| Logging | Structlog |

---

## 📁 Project Structure

```
revops-ai/  
├── backend/  
│   ├── main.py  
│   ├── config/settings.py  
│   ├── agents/  
│   ├── tools/  
│   ├── memory/  
│   ├── models/  
│   ├── data/  
│   └── utils/  
└── frontend/  
    └── src/
```

---

## ✨ Key Features

-   🔁 **LangGraph Workflows** — Modular, state-driven execution
    
-   🤖 **Autonomous Agents** — Independent reasoning + retries
    
-   🧠 **FAISS Memory** — Persistent personalization
    
-   📊 **Preloaded CRM Dataset** — Realistic testing environment
    
-   🔍 **Explainability Layer** — Transparent AI decisions
    
-   🛠️ **Failure Recovery System** — Auto retry + fallback + escalation
    
-   🧪 **Mock Mode** — Works without external dependencies
    

---

## 🎯 Use Cases

-   Automated B2B sales outreach
    
-   CRM optimization & hygiene
    
-   Deal risk monitoring
    
-   Customer retention strategies
    
-   Revenue intelligence dashboards
    

---

## 📌 Notes

-   Designed for **demo + production extensibility**
    
-   Easily pluggable with real CRM systems (Salesforce, HubSpot)
    
-   Supports scaling to **multi-tenant SaaS architecture**
    

---
