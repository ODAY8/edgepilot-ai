# EdgePilot AI — Backend

FastAPI backend for EdgePilot AI. `/api/analyze` runs a real pipeline:
Google Gemini analyzes the actual uploaded image/video frame (real vision,
no random guessing), a deterministic rule-based engine scores the risk,
and Groq generates the natural-language explanation and recommended
action. Both AI providers are genuinely separate — a vision-only model
and a text-only model, called independently.

## Stack

- Python 3.11+
- FastAPI + Uvicorn
- Pydantic v2 schemas
- SQLite (stdlib `sqlite3`, no ORM)
- Google Gemini for real vision analysis (required for `/api/analyze`)
- Groq for LLM-backed reasoning (optional, falls back to templates)
- OpenCV (headless) for extracting a frame from uploaded video

## Setup

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env   # then fill in GEMINI_API_KEY (required) and GROQ_API_KEY (optional)
```

## Run

```bash
# Loads .env so GEMINI_API_KEY / GROQ_API_KEY actually take effect:
uvicorn app.main:app --reload --port 8000 --env-file .env
```

Startup logs confirm what's actually enabled:

```
Vision analysis (Gemini): enabled
Groq reasoning: enabled
```

If `Vision analysis (Gemini)` says `DISABLED`, every call to
`/api/analyze` will return `503` — this is intentional (see below), not
a bug.

- API root: http://localhost:8000/
- Interactive docs (Swagger UI): http://localhost:8000/docs
- OpenAPI schema: http://localhost:8000/openapi.json

A SQLite file (`edgepilot.db`, path configurable via `DATABASE_PATH`) is
created next to `backend/` on first run and seeded with demo incidents,
so `/api/incidents` returns realistic data immediately even before any
real analysis has run.

## Endpoints

| Method | Path                                | Description                                   |
|--------|--------------------------------------|------------------------------------------------|
| GET    | `/api/health`                        | Service health check                           |
| POST   | `/api/analyze`                       | Upload an image/video, run the real pipeline, persist an incident |
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
curl -F "file=@photo.jpg;type=image/jpeg" -F "location=Zone A" http://localhost:8000/api/analyze
```

Response:

```json
{
  "id": "INC-AB12CD",
  "event": { "type": "restricted_area_entry", "label": "Restricted Area Entry", "confidence": 0.99 },
  "risk": { "level": "HIGH", "score": 87 },
  "analysis": { "summary": "...", "explanation": "..." },
  "recommendation": { "action": "...", "priority": "IMMEDIATE" }
}
```

If vision analysis fails or isn't configured, the response is a `503`
with a `detail` message instead — never a fabricated result. If the
uploaded video can't be decoded, it's a `422`.

## Architecture

```
upload (image, or video → frame_extraction.extract_frame)
    → vision.detect_event (Gemini, REQUIRED, no fallback)
    → risk.assess_risk (deterministic lookup table)
    → llm.generate_reasoning (Groq)  --- falls back to ---→ reasoning.generate_explanation
                                                           + recommendations.recommend_action
    → database.insert_incident → response
```

Each stage lives in its own module under `app/services/` with a narrow,
typed function signature: `vision.py`, `frame_extraction.py`, `risk.py`,
`llm.py`, `reasoning.py`, `recommendations.py`.

**Vision and reasoning are two independent AI calls to two independent
providers** — `vision.py` only ever talks to Gemini for image
classification; `llm.py` only ever talks to Groq for text generation.
Neither knows the other exists. This is deliberate: a text LLM cannot
see an image, so the "AI saw X" claim has to come from a model that
actually received the pixels.

### Real vision analysis (required)

Unlike Groq reasoning, **there is no fallback for vision** — this was a
explicit requirement, not an oversight. Returning a random/fake
detection when the vision model is unavailable would mean claiming the
system observed something it never analyzed. So:

- `vision.detect_event()` raises `VisionUnavailableError` if
  `GEMINI_API_KEY` is unset or the Gemini call fails for any reason.
- `routes/analysis.py` turns that into a `503` response.
- No incident is ever created from a detection the vision model didn't
  actually produce.

Setup:
1. Get a free API key at https://aistudio.google.com/apikey.
2. Put it in `backend/.env`: `GEMINI_API_KEY=...`
3. Run uvicorn with `--env-file .env` (see above).
4. Check the startup log: `Vision analysis (Gemini): enabled`.

`GEMINI_MODEL` defaults to `gemini-flash-lite-latest` — a "-latest"
alias that auto-tracks Google's current fastest model for this tier,
rather than a dated model id. This is deliberate: during this project's
development, both `gemini-2.0-flash` and later `gemini-2.5-flash-lite`
were deprecated/retired out from under us. Pin to a specific dated
model (e.g. `gemini-3.5-flash-lite`) in `.env` instead if you want fully
reproducible behavior over auto-updating behavior. If it 404s, list
what's actually available on your account:

```bash
python -c "from google import genai; import os; [print(m.name) for m in genai.Client(api_key=os.environ['GEMINI_API_KEY']).models.list()]"
```

The model is asked to return strict JSON — `event_type` (constrained to
a fixed set: `restricted_area_entry`, `forklift_near_miss`,
`ppe_violation`, `unattended_object`, `normal_activity`), `confidence`,
and `context` (a factual description of what it actually observed,
not a canned string). Video uploads get one representative frame
extracted via OpenCV (`frame_extraction.py`) before being sent through
the same path as an image.

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

Unlike vision, if Groq isn't configured or the call fails, `llm.py`
returns `None` and `routes/analysis.py` falls back to the fixed-string
templates in `reasoning.py`/`recommendations.py` — a real detection
described in slightly less eloquent, canned language is an acceptable
degradation; a fabricated detection is not.

`app/database/database.py` is a thin `sqlite3` wrapper: schema, seed
data, and queries for incidents plus the derived dashboard/analytics
stats. No ORM, so it's easy to read end-to-end.

`app/models/schemas.py` defines every request/response shape. Incident,
dashboard, and analytics fields intentionally use the same camelCase
names as `src/data/types.ts` on the frontend, so wiring up `api.ts`
later needs no field-mapping layer.

## Known placeholders (by design, this phase)

- `services/risk.py` is a static event-type → risk-level lookup table,
  not a learned or LLM-driven assessment (kept deterministic on purpose).
- `dashboard/stats`'s `change` fields are always `0` — trend deltas need
  a stats-history table, which doesn't exist yet.
- `analytics`'s `uptime`/`avgResponseTime` are static strings — no real
  infra telemetry is being collected yet.
- No live camera ingestion yet (browser webcam capture planned as a
  separate phase) — `/api/analyze` is still a one-shot file upload.

## Tests run during this phase

Verified with synthetic test images (not the placeholder catalog —
actual generated scenes) that Gemini correctly discriminates between a
hazardous scene (person inside a marked restricted zone with hazard
stripes → `restricted_area_entry`, 0.99 confidence, accurate
description) and a benign scene (person near ordinary boxes →
`normal_activity`, 0.95 confidence) using `gemini-3.5-flash-lite` and
the default `gemini-flash-lite-latest` alias. All existing endpoints
re-verified via `curl` after the change: health, incident list/get/
acknowledge/escalate, dashboard stats, analytics.
