# EdgePilot AI — Backend

FastAPI backend for EdgePilot AI. See the [project root README](../README.md) for the full picture (positioning, pipeline, frontend, demo flow); this document covers the backend specifically.

`/api/analyze` and `/api/analyze-frame` run the same real pipeline: Google Gemini analyzes the actual image/frame (object recognition, scene description, and safety-event detection — real vision, no random guessing), a deterministic rule-based engine scores the risk, and Groq generates a natural-language explanation and recommended action (skipped only on the live-camera path for routine `normal_activity`/cooldown frames — see below). Vision and reasoning are two independent AI calls to two independent providers — a vision-only model and a text-only model — neither knows the other exists.

## Stack

- Python 3.11+
- FastAPI + Uvicorn
- Pydantic v2 schemas
- SQLite (stdlib `sqlite3`, no ORM)
- Google Gemini (`google-genai`) for real vision analysis — object recognition, scene description, and safety-event detection in one call (required for `/api/analyze*`)
- Groq for LLM-backed reasoning (optional — falls back to fixed templates if unset or unavailable)
- OpenCV (headless) for extracting a representative frame from an uploaded video
- `python-dotenv` for loading `backend/.env`

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
uvicorn app.main:app --reload --port 8000
```

`app/main.py` loads `backend/.env` itself on startup (via `python-dotenv`, `override=False`) — no `--env-file` flag is needed. A real exported environment variable (or a production secrets manager) always takes priority over whatever is in `.env`.

Startup logs confirm what's actually enabled:

```
Vision analysis (Gemini): enabled
Groq reasoning: enabled
```

If `Vision analysis (Gemini)` says `DISABLED`, every call to `/api/analyze` or `/api/analyze-frame` will return `503` — this is intentional (see below), not a bug.

- API root: http://localhost:8000/
- Interactive docs (Swagger UI): http://localhost:8000/docs
- OpenAPI schema: http://localhost:8000/openapi.json

A SQLite file (`edgepilot.db`, path configurable via `DATABASE_PATH`) is created next to `backend/` on first run and seeded with demo incidents, so `/api/incidents` returns realistic data immediately even before any real analysis has run.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET    | `/api/health` | Service health check |
| POST   | `/api/analyze` | Upload an image/video, run the real pipeline, persist an incident |
| POST   | `/api/analyze-frame` | Analyze one live browser-camera frame (see below for the policy layer on top of the same pipeline) |
| GET    | `/api/incidents` | List all incidents |
| GET    | `/api/incidents/{incident_id}` | Get one incident |
| POST   | `/api/incidents/{incident_id}/acknowledge` | Mark an incident acknowledged |
| POST   | `/api/incidents/{incident_id}/escalate` | Mark an incident escalated |
| GET    | `/api/dashboard/stats` | Dashboard overview metrics, computed live from the database |
| GET    | `/api/insights` | Chart data for the frontend's Analytics page (events over time, risk mix, event categories) |
| GET    | `/api/system/status` | Non-secret config status for the Settings page (version, whether Gemini/Groq are configured) — never returns key values |

**Note on `/api/insights`:** the frontend page and route are still called "Analytics" — only this backend path is named differently. Ad-blocker/privacy filter lists (e.g. EasyPrivacy) commonly block any request path containing the substring "analytics," which broke this exact endpoint for real users even though nothing was actually wrong with it. See `app/routes/analytics.py` (file name unchanged; only the route path changed) and `src/services/api.ts` on the frontend.

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
  "event": { "type": "restricted_area_entry", "label": "Restricted Area Entry", "confidence": 0.97 },
  "risk": { "level": "HIGH", "score": 91 },
  "analysis": { "summary": "...", "explanation": "..." },
  "recommendation": { "action": "...", "priority": "IMMEDIATE" },
  "objects": [
    { "name": "person", "confidence": 0.98, "context": "standing inside the marked zone" },
    { "name": "restricted area sign", "confidence": 0.95, "context": "visible on the barrier" }
  ],
  "sceneDescription": "A person is standing inside a marked restricted zone."
}
```

`objects` and `sceneDescription` come from the same Gemini call as `event` and are independent of it — general object/scene recognition never influences safety-event detection (see `app/services/vision.py`).

If vision analysis fails or isn't configured, the response is a `503` with a `detail` message instead — never a fabricated result. If the uploaded video can't be decoded, it's a `422`.

### `POST /api/analyze-frame`

Same `multipart/form-data` shape as `/api/analyze` (image only — no video), plus the same required `file` field and optional `camera_id`/`location`. Reuses the exact same vision/risk/reasoning/database services as `/api/analyze`; this route only adds the policy layer needed for a frame arriving every few seconds from a live feed:

- **`normal_activity` never creates an incident.** No database write, no Groq call — most frames land here.
- **Cooldown/deduplication** (`app/services/dedup.py`): once a `(camera_id, event_type)` pair creates an incident, further incidents for that same pair are suppressed for `LIVE_EVENT_COOLDOWN_SECONDS` (default 60) so one ongoing event doesn't spam a new incident and a new Groq call every few seconds. The tracker is an in-process dict, not persisted or shared across workers — sufficient for a single-process deployment; a multi-worker production deployment would move this to Redis or a database table keyed the same way.
- Only a genuinely new, non-cooldown, non-normal event calls Groq and persists an incident.

Response:

```json
{
  "incidentCreated": true,
  "status": "CREATED",
  "event": { "type": "ppe_violation", "label": "PPE Violation", "confidence": 0.88 },
  "risk": { "level": "MEDIUM", "score": 63 },
  "incidentId": "INC-7F3A2C",
  "analysis": { "summary": "...", "explanation": "..." },
  "recommendation": { "action": "...", "priority": "HIGH" },
  "objects": [{ "name": "person", "confidence": 0.97, "context": "not wearing a hard hat" }],
  "sceneDescription": "A person is working near machinery without a hard hat."
}
```

`status` is `"NORMAL"` (no incident, `incidentCreated: false`), `"COOLDOWN"` (meaningful event but suppressed, `incidentCreated: false`), or `"CREATED"` (a new incident was persisted). `incidentId`/`analysis`/`recommendation` are `null` for `NORMAL`/`COOLDOWN`. `objects`/`sceneDescription` are populated on every response regardless of `status`.

If vision analysis fails, this also returns `503` — a failed live frame is surfaced as "Vision Unavailable" on the frontend, never presented as a stale "All Clear."

## Architecture

```
image (upload, or a frame extracted from video via frame_extraction.py)
    │
    ▼
vision.detect_event (Gemini, REQUIRED, no fallback)
    -- one call returns: objects[], scene_description, and the safety event
    -- (type, confidence, context, evidence_visible)
    -- evidence-based backstop: a non-normal event is downgraded back to
    -- normal_activity unless evidence_visible=true AND confidence >= 0.6
    │
    ▼
risk.assess_risk (deterministic event-type → score-band lookup, no randomness)
    │
    ▼
[/api/analyze-frame only] dedup.should_create_incident (cooldown check)
    │
    ▼
llm.generate_reasoning (Groq) --- falls back to ---> reasoning.generate_explanation
                                                    + recommendations.recommend_action
    │
    ▼
database.insert_incident → response
```

Each stage lives in its own module under `app/services/` with a narrow, typed function signature: `vision.py`, `frame_extraction.py`, `risk.py`, `dedup.py`, `llm.py`, `reasoning.py`, `recommendations.py`.

### Real vision analysis (required, no fallback)

Unlike Groq reasoning, **there is no fallback for vision** — this is an explicit requirement, not an oversight. Returning a fabricated detection when the vision model is unavailable would mean claiming the system observed something it never analyzed. So:

- `vision.detect_event()` raises `VisionUnavailableError` if `GEMINI_API_KEY` is unset or the Gemini call fails for any reason.
- `routes/analysis.py` and `routes/live.py` both turn that into a `503` response.
- No incident is ever created from a detection the vision model didn't actually produce.

Gemini is sent the image plus a prompt asking for one JSON response covering two independent parts: general object/scene recognition (up to 15 objects, each with a name/confidence/context, plus one scene-description sentence — instructed not to guess if uncertain), and safety-event classification into one of `restricted_area_entry`, `forklift_near_miss`, `ppe_violation`, `unattended_object`, `normal_activity`, each with its own strict per-type evidence requirements in the prompt. Recognizing an object (a person, a forklift, a sign) is explicitly never sufficient on its own to imply the corresponding safety event.

`GEMINI_MODEL` defaults to `gemini-flash-lite-latest` — a `-latest` alias that auto-tracks Google's current fastest model for this tier, rather than a dated model id. This is deliberate: dated Gemini model ids have been deprecated/retired multiple times during this project's development. Pin to a specific dated model instead if you want fully reproducible behavior over auto-updating behavior. If it 404s, list what's actually available on your account:

```bash
python -c "from google import genai; import os; [print(m.name) for m in genai.Client(api_key=os.environ['GEMINI_API_KEY']).models.list()]"
```

Video uploads get one representative frame extracted via OpenCV (`frame_extraction.py`) before being sent through the same path as an image.

### Deterministic risk scoring

`services/risk.py` is a static `event type → (risk level, score band)` lookup table. The score within the band is a pure function of Gemini's own confidence for that detection — same `(event type, confidence)` always yields the same `(level, score)`. No randomness, no model call, nothing time-dependent.

### Real AI reasoning (optional, only for meaningful events)

1. Get a free API key at https://console.groq.com/keys.
2. Put it in `backend/.env`: `GROQ_API_KEY=gsk_...`
3. Check the startup log line: `Groq reasoning: enabled`.

`GROQ_MODEL` defaults to `openai/gpt-oss-120b`; override it in `.env` to try a different Groq-hosted model. If you get a `model_not_found` 404, list what's currently available:

```bash
python -c "from groq import Groq; import os; [print(m.id) for m in Groq(api_key=os.environ['GROQ_API_KEY']).models.list().data]"
```

Reasoning models (like the `gpt-oss` family) spend part of their token budget on an internal reasoning trace before the final JSON — `llm.py` passes `reasoning_effort="low"` for any model with `gpt-oss` in its name to keep that fast, and requests `max_tokens=1024` so the trace doesn't crowd out the actual answer.

Unlike vision, if Groq isn't configured or the call fails, `llm.py` returns `None` and the caller falls back to the fixed-string templates in `reasoning.py`/`recommendations.py` — a real detection described in slightly less eloquent, canned language is an acceptable degradation; a fabricated detection is not.

On the live camera path (`/api/analyze-frame`), Groq is only ever called for a genuinely new, non-cooldown, non-`normal_activity` event — not on every frame. On the one-shot upload path (`/api/analyze`), Groq (or its template fallback) always runs for whatever Gemini detected, including `normal_activity`, since a single deliberate upload always gets a real answer.

`app/database/database.py` is a thin `sqlite3` wrapper: schema, seed data, and queries for incidents plus the derived dashboard/insights stats. No ORM, so it's easy to read end-to-end.

`app/models/schemas.py` defines every request/response shape. Incident, dashboard, and insights fields intentionally use the same camelCase names as `src/data/types.ts` on the frontend, so `src/services/api.ts` needs no field-mapping layer.

## Known simplifications (by design)

- `services/risk.py` is a static lookup table, not a learned or LLM-driven assessment (kept deterministic and auditable on purpose).
- `dashboard/stats`'s `change` fields are always `0` — trend deltas would need a stats-history table, which doesn't exist yet.
- `/api/insights`'s `uptime`/`avgResponseTime` are static strings — no real infra telemetry is being collected yet.
- The cooldown tracker in `dedup.py` is in-process memory — it resets on restart and isn't shared across multiple worker processes.
- No authentication on any endpoint — anyone who can reach the API can list/acknowledge/escalate incidents. Fine for a local demo, not for a public deployment.

## Tests

```bash
pytest tests/ -v
```

Covers: deterministic risk scoring across all event types and confidence ranges; Gemini vision parsing and the evidence-based backstop (mocked, plus a few tests that hit the real Gemini API when `GEMINI_API_KEY` is set); `/api/system/status` never leaking key material; and the `.env` auto-loading behavior in `app/main.py`.
