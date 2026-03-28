# RevOps AI Backend

Production-hardened FastAPI backend for the RevOps AI agentic system.

## What’s Included

- Access + refresh JWT auth with issuer/audience validation
- Refresh rotation, replay detection, and revocation storage
- RBAC (`admin`, `user`) persisted in the user store
- Mongo-backed products, sessions, refresh tokens, and audit logging
- Soft-delete products plus pagination/filtering on list endpoints
- Planner → executor → validator orchestration pipeline with guardrails
- Structured JSON logging, request IDs, user-scoped audit logs, and basic metrics
- User-namespaced vector memory with TTL and size limits
- Basic test coverage for auth, product CRUD, and one workflow

## Key Endpoints

- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET /auth/me`
- `POST /products`
- `GET /products`
- `PUT /products/{product_id}`
- `DELETE /products/{product_id}`
- `POST /run-outreach`
- `POST /detect-risk`
- `POST /predict-churn`
- `GET /logs`
- `GET /sessions`
- `GET /metrics`
- `GET /health`

## Backend Structure

```text
backend/
├── agents/
│   ├── orchestrator.py
│   ├── guardrails.py
│   ├── failure_recovery.py
│   └── *_agent.py
├── auth/
│   ├── deps.py
│   ├── jwt.py
│   └── passwords.py
├── config/
│   └── settings.py
├── db/
│   └── mongo.py
├── memory/
│   └── vector_store.py
├── models/
│   └── schemas.py
├── repositories/
│   ├── users.py
│   ├── products.py
│   ├── sessions.py
│   └── refresh_tokens.py
├── services/
│   ├── auth_service.py
│   ├── observability.py
│   └── rate_limit.py
├── tests/
│   ├── conftest.py
│   ├── test_auth_products.py
│   └── test_agent_flow.py
├── tools/
├── utils/
├── deps.py
└── main.py
```

## Local Run

```bash
cp .env.example .env
cd backend
pip install -r requirements.txt
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

## Production Run

1. Set `ENVIRONMENT=production`.
2. Set a real `AUTH_SECRET_KEY` with 32+ random characters.
3. Point `MONGODB_URI` to your production Mongo cluster.
4. Set `AUTH_COOKIE_SECURE=true` and production `CORS_ORIGINS`.
5. Provide your real LLM and email credentials.
6. Run with a process manager, for example:

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 2
```

## Tests

```bash
python -m pytest backend/tests -q
```
