# EdgePilot AI — Backend

FastAPI backend for EdgePilot AI. Started as a persistent API surface with
a fully placeholder detection pipeline; reasoning + recommendation are now
optionally backed by a real Groq LLM call, with the original rule-based
templates kept as an automatic fallback. Vision (event detection) is still
a placeholder — no vision model is wired in yet.

## Stack

- Python 3.11+
- FastAPI + Uvicorn
- Pydantic v2 schemas
- SQLite (stdlib `sqlite3`, no ORM)
- Groq (optional) for LLM-backed reasoning

## Setup

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env   # optional for everything except Groq — see below
```

## Run

```bash
uvicorn app.main:app --reload --port 8000

# or, to actually load .env (needed for GROQ_API_KEY):
uvicorn app.main:app --reload --port 8000 --env-file .env
```

Startup logs say whether Groq reasoning is enabled or falling back to
templates, so you can confirm your key took effect without needing to
run an analysis first.

- API root: http://localhost:8000/
- Interactive docs (Swagger UI): http://localhost:8000/docs
- OpenAPI schema: http://localhost:8000/openapi.json

A SQLite file (`edgepilot.db`, path configurable via `DATABASE_PATH`) is
created next to `backend/` on first run and seeded with the same demo
incidents used by the frontend's mock data, so `/api/incidents` returns
realistic data immediately.

## Endpoints

| Method | Path                                | Description                                   |
|--------|--------------------------------------|------------------------------------------------|
| GET    | `/api/health`                        | Service health check                           |
| POST   | `/api/analyze`                       | Upload an image/video, run the placeholder pipeline, persist an incident |
| GET    | `/api/incidents`                     | List all incidents                             |
| GET    | `/api/incidents/{incident_id}`       | Get one incident                               |
| POST   | `/api/incidents/{incident_id}/acknowledge` | Mark an incident acknowledged             |
| POST   | `/api/incidents/{incident_id}/escalate`    | Mark an incident escalated                |
| GET    | `/api/dashboard/stats`               | Dashboard overview metrics                     |
| GET    | `/api/analytics`                     | Chart data (events over time, risk mix, categories) |

### `POST /api/analyze`

`multipart/form-data`:

- `file` (required) — image or video
- `location` (optional)
- `camera_id` (optional)

```bash
curl -F "file=@clip.mp4;type=video/mp4" -F "location=Zone A" http://localhost:8000/api/analyze
```

Response:

```json
{
  "id": "INC-AB12CD",
  "event": { "type": "restricted_area_entry", "label": "Restricted Area Entry", "confidence": 0.94 },
  "risk": { "level": "HIGH", "score": 87 },
  "analysis": { "summary": "...", "explanation": "..." },
  "recommendation": { "action": "...", "priority": "IMMEDIATE" }
}
```

## Architecture

```
upload → vision.detect_event → risk.assess_risk
       → llm.generate_reasoning (Groq)  --- falls back to ---→ reasoning.generate_explanation
                                                              + recommendations.recommend_action
       → database.insert_incident → response
```

Each stage lives in its own module under `app/services/` with a narrow,
typed function signature (`services/vision.py`, `services/risk.py`,
`services/reasoning.py`, `services/recommendations.py`, `services/llm.py`).
`services/llm.py` never raises: if `GROQ_API_KEY` isn't set, or the API
call fails for any reason (network, rate limit, malformed JSON), it
returns `None` and `routes/analysis.py` falls back to the original
rule-based templates — the pipeline is never taken down by a third-party
outage. Swapping the vision placeholder for a real model later means
editing the inside of `vision.detect_event`, not the pipeline wiring.

### Real AI reasoning (optional)

1. Get a free API key at https://console.groq.com/keys.
2. Put it in `backend/.env`: `GROQ_API_KEY=gsk_...`
3. Run uvicorn with `--env-file .env` (see above).
4. Check the startup log line: `Groq reasoning: enabled`.

`GROQ_MODEL` defaults to `openai/gpt-oss-120b`; override it in `.env` to
try a different Groq-hosted model. Model availability on Groq changes
over time — if you get a `model_not_found` 404, list what's currently
available on your account:

```bash
python -c "from groq import Groq; import os; [print(m.id) for m in Groq(api_key=os.environ['GROQ_API_KEY']).models.list().data]"
```

Note that reasoning models (like the `gpt-oss` family) spend part of
their token budget on an internal reasoning trace before the final JSON
— `llm.py` passes `reasoning_effort="low"` for any model with `gpt-oss`
in its name to keep that fast, and requests `max_tokens=1024` so the
trace doesn't crowd out the actual answer.

The LLM is prompted to return strict JSON (`summary`, `explanation`,
`action`, `priority`) so it slots directly into the existing
`AnalyzeResponse` shape — no frontend changes needed. Vision detection
(which event is picked) and risk scoring are still placeholders; only
the explanation and recommended action text are LLM-generated when a
key is configured.

`app/database/database.py` is a thin `sqlite3` wrapper: schema, seed
data, and queries for incidents plus the derived dashboard/analytics
stats. No ORM, so it's easy to read end-to-end.

`app/models/schemas.py` defines every request/response shape. Incident,
dashboard, and analytics fields intentionally use the same camelCase
names as `src/data/types.ts` on the frontend, so wiring up `api.ts`
later needs no field-mapping layer.

## Known placeholders (by design, this phase)

- `services/vision.py` picks a detection at random from a small catalog
  instead of running a real model.
- `services/risk.py` is a static event-type → risk-level lookup table,
  not a learned or LLM-driven assessment.
- `dashboard/stats`'s `change` fields are always `0` — trend deltas need
  a stats-history table, which doesn't exist yet.
- `analytics`'s `uptime`/`avgResponseTime` are static strings — no real
  infra telemetry is being collected yet.

## Tests run during this phase

All endpoints were exercised manually via `curl` against a running
`uvicorn` instance: health check, full incident list/get/acknowledge/
escalate cycle, dashboard stats, analytics, and an end-to-end file
upload through `/api/analyze` (confirmed it also creates a new row
visible in a subsequent `/api/incidents` call). See the PR/commit
description for captured output.
