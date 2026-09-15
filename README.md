# EdgePilot AI

An AI-powered edge monitoring and safety intelligence platform for industrial/warehouse environments.

EdgePilot watches a camera feed (a browser webcam, or an uploaded photo/video), uses Google Gemini to understand what's actually in the frame, runs a deterministic risk engine, and asks Groq to write a plain-language explanation and recommended action — for live camera monitoring, only when there's a genuinely new event worth a human's attention; for a deliberate one-shot upload, always. Every result lands on a dashboard for a human operator to acknowledge or escalate.

## What this actually is

**This is a browser-camera edge monitoring prototype**, not a deployed hardware system. Concretely:

- The "camera" is your browser's webcam (via `getUserMedia`) or a file you upload — there is no physical edge device, no Jetson/Raspberry Pi, no robot, and no industrial camera integration in this codebase.
- "Edge node" labels in the UI (e.g. `BROWSER EDGE NODE`, `EDGE NODE 01`) are illustrative naming for the demo, not references to real deployed hardware.
- Everything runs as a normal web app: a React frontend in the browser, talking to a FastAPI backend on your machine (or wherever you deploy it), talking out to Gemini and Groq over the internet.

That's a deliberate, honest scope for a hackathon prototype: the interesting part is the real, working AI pipeline and the operator-facing product around it — not custom hardware.

## The pipeline

```
Browser webcam (getUserMedia) or an uploaded image/video
        │
        ▼
Gemini Vision  ──►  object + scene recognition   (independent of the line below)
        │
        ▼
safety-event detection (evidence-gated)
        │
        ▼
deterministic risk engine  (event type + confidence → risk level + score)
        │
        ▼
cooldown / deduplication   (live camera only — skips repeat incidents)
        │
        ▼
Groq reasoning   (live camera: only for a new, non-cooldown, meaningful event
                  one-shot upload: always runs, for whatever was detected)
        │
        ▼
incident (persisted to SQLite)
        │
        ▼
dashboard  →  human decision (acknowledge / escalate)
```

Object/scene recognition and safety-event detection come from **one Gemini call** that does two independent jobs at once — recognizing a forklift or a warning sign as an *object* never by itself implies the corresponding *safety event* is happening. See [Gemini's role](#geminis-role) below.

The cooldown/dedup and "skip normal frames" steps only apply to the **live camera** path (`/api/analyze-frame`); a one-shot upload via the Analyze page (`/api/analyze`) always creates an incident and always calls Groq for whatever Gemini detected, since a deliberate single upload is always something the operator explicitly asked to analyze — see [Groq's role](#groqs-role-reasoning) below.

## Gemini's role

Every frame (upload or live) goes to Gemini exactly once, which returns a single JSON response covering:

- **Visual perception** — Gemini is the only component in this system that actually looks at pixels. No other stage ever "sees" the image.
- **Object recognition** — up to 15 of the most relevant objects visible in the frame (person, forklift, laptop, warning sign, PPE, etc.), each with a name, confidence, and short context string. Gemini is instructed not to guess — if it's not confident an object is present, it's told to omit it rather than hallucinate it.
- **Scene description** — one plain-language sentence describing the overall scene.
- **Safety-event detection** — a classification into one of a fixed set of event types (see below), gated by strict, per-event evidence requirements in the prompt. A person merely being visible is never enough on its own; e.g. `restricted_area_entry` requires *both* a visibly marked/signed restricted area *and* a person inside it.

Event types: `restricted_area_entry`, `forklift_near_miss`, `ppe_violation`, `unattended_object`, `normal_activity`.

Beyond the prompt, there's a **code-level backstop** in `backend/app/services/vision.py`: any non-`normal_activity` classification is downgraded back to `normal_activity` if Gemini itself didn't mark clear evidence as visible (`evidence_visible: false`), or if its confidence is below `0.6` — regardless of what the model claims, both checks have to pass before a safety event is trusted.

There is **no fallback** for vision: if `GEMINI_API_KEY` isn't set or the Gemini call fails, the backend raises a clear error (`503`) instead of ever fabricating a detection.

## The deterministic risk engine

`backend/app/services/risk.py` turns a `(safety event, confidence)` pair into a risk level and a 0–100 score, with **zero randomness**:

1. The event type selects a fixed score *band* — e.g. `restricted_area_entry` → `HIGH`, band 85–96; `ppe_violation` → `MEDIUM`, band 55–72; `normal_activity` → `LOW`, band 2–15.
2. Gemini's own confidence for that detection places the score within the band — higher confidence pushes the score toward the top of the band, lower confidence toward the bottom.
3. The same `(event type, confidence)` pair always produces the exact same `(level, score)` — this is a pure lookup-table function, not a model or a dice roll.

This is intentionally simple and auditable — the seam where a more sophisticated, rules-based or model-driven risk engine could plug in later without changing anything upstream or downstream of it.

## Groq's role (reasoning)

Groq is a **separate, text-only model** — it never sees the image, only a structured summary of what Gemini and the risk engine already produced (event type, label, confidence, context, risk level, score, location). Its job:

- Write a short natural-language **explanation** of what happened.
- Recommend a concrete operator **action**.
- Assign a **priority** (`IMMEDIATE` / `HIGH` / `MEDIUM` / `LOW`).

On the **live camera** path (`/api/analyze-frame`), Groq is called **only when there's something worth reasoning about** — a genuinely new, non-`normal_activity` event that isn't currently in cooldown (see [Live monitoring](#live-monitoring) below). The vast majority of live frames (`normal_activity`, or a repeat event still in cooldown) never trigger a Groq call at all, by design — no need to spend an LLM call explaining that nothing happened, and no incident is created for them either.

On the **one-shot upload** path (`/api/analyze`, used by the Analyze page), there's no such gate: every uploaded image/video gets a Groq call and an incident, whatever Gemini detected — including `normal_activity` — since a deliberate, single upload is always something the operator explicitly asked to analyze.

If `GROQ_API_KEY` isn't set, or the Groq call fails for any reason, the backend falls back to fixed-string templates (`reasoning.py` / `recommendations.py`) instead of blocking the pipeline — a real detection described in plainer, canned language is an acceptable degradation; a fabricated detection is not.

## Live monitoring

The Dashboard's camera panel (`src/components/dashboard/CameraPanel.tsx`) drives live monitoring entirely from the browser:

- Requests the webcam via `navigator.mediaDevices.getUserMedia`.
- Captures a frame to an in-memory `<canvas>` and POSTs it to `/api/analyze-frame` roughly **every 4 seconds** (`CAPTURE_INTERVAL_MS = 4000`), with an in-flight guard so overlapping requests can't pile up if the network is slow.
- Tags every frame with a camera ID — `CAM-LIVE-01` by default for the browser feed (configurable via a prop).
- **Normal frames never create an incident.** A `normal_activity` result just updates the live "All Clear" state on the dashboard — no database write, no Groq call.
- **Cooldown prevents duplicate incidents.** Once a given `(camera, event type)` pair creates an incident, the backend (`services/dedup.py`) suppresses further incidents for that same pair for `LIVE_EVENT_COOLDOWN_SECONDS` (default 60s) — so one ongoing event doesn't spam a new incident (and a new Groq call) every few seconds while it's still happening. The cooldown tracker is in-process memory, not persisted.

## Degraded operation

The UI is built to never claim more certainty than it actually has:

- **Vision Unavailable** — if a live frame's analysis request fails (Gemini misconfigured, network error, quota exhausted, etc.), the dashboard shows an explicit "Vision Unavailable" state instead of silently keeping a stale "All Clear" or a stale old incident on screen. Monitoring resumes automatically the moment the next frame succeeds.
- **API errors** — every page (Dashboard, Incidents, Analytics/Insights, Analyze) shows a dedicated error state with a retry action if its backend call fails, instead of rendering blank or throwing.
- **Camera permission denied** — if the browser denies camera access, the panel shows a clear "Camera Permission Denied" state with a retry action.
- **Camera unavailable** — if no camera device can be found or `getUserMedia` fails for another reason, the panel shows a "Camera Unavailable" state.
- **A page-level crash never blanks the whole app.** Every routed page is wrapped in an error boundary (`src/components/common/ErrorBoundary.tsx`) so a failure in one page shows a scoped "This page failed to load" message with a reload action, instead of taking down the sidebar/navigation with it. Lazy-loaded page chunks also get one automatic reload-and-retry (`src/lazyImport.ts`) if their initial fetch fails — e.g. after a dev-server restart, or a browser extension transiently interfering with a request.

## Dashboard pages

| Page | Route | What it does |
|---|---|---|
| **Dashboard** | `/dashboard` | Real-time overview: live camera panel, current incident / All Clear / Vision Unavailable state, live stat cards (from `/api/dashboard/stats`), and the recent event timeline. |
| **Analyze** | `/analyze` | Upload a single image or video for one-shot analysis. Shows a processing view driven by the real request lifecycle (not a fake timer), then the result with Acknowledge/Escalate actions. |
| **Incidents** | `/incidents` | Full incident history from the real database, with risk-level/status filters, a detail view, and Acknowledge/Escalate actions. |
| **Analytics** | `/analytics` | Charts over real incident data: events over time, risk distribution, and top event categories. (The page and route are still called "Analytics" in the UI — see the note on `/api/insights` below.) |
| **Settings** | `/settings` | Non-secret system status: API reachability, whether Gemini vision / Groq reasoning are configured, whether this browser supports live camera capture, and the backend version. Never displays API keys or credentials. |

## API endpoints

All routes are prefixed with `/api` and served by FastAPI (interactive docs at `/docs` when the backend is running).

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Service health check. |
| POST | `/api/analyze` | Upload one image or video; runs the full pipeline once and persists an incident. |
| POST | `/api/analyze-frame` | Analyze one live camera frame; only creates an incident for a new, non-cooldown safety event. |
| GET | `/api/incidents` | List all incidents. |
| GET | `/api/incidents/{incident_id}` | Get one incident. |
| POST | `/api/incidents/{incident_id}/acknowledge` | Mark an incident acknowledged. |
| POST | `/api/incidents/{incident_id}/escalate` | Mark an incident escalated. |
| GET | `/api/dashboard/stats` | Dashboard overview metrics, computed live from the database. |
| GET | `/api/insights` | Chart data for the Analytics page (events over time, risk mix, event categories). **Note:** this endpoint is deliberately *not* named `/api/analytics` — ad-blocker/privacy filter lists commonly block any request path containing "analytics," which broke this exact call for real users. The frontend route and visible page name are still "Analytics"; only the backend path changed. |
| GET | `/api/system/status` | Non-secret config status for the Settings page (version, whether Gemini/Groq are configured). Never returns key values. |

### `POST /api/analyze` response shape

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

If vision analysis fails or isn't configured, the response is a `503` with a `detail` message — never a fabricated result. An undecodable video upload returns `422`.

### `POST /api/analyze-frame` response shape

Same `event`/`risk`/`objects`/`sceneDescription` shape as above, plus a `status` field describing what the backend actually did with this frame, and incident info only when one was created:

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

`status` is one of:
- `"NORMAL"` — `normal_activity`; `incidentCreated: false`, `incidentId`/`analysis`/`recommendation` are `null`.
- `"COOLDOWN"` — a meaningful event, but the same `(camera, event type)` already has an incident within the cooldown window; `incidentCreated: false`, no new Groq call was made.
- `"CREATED"` — a genuinely new, meaningful event; a real incident was persisted and Groq (or the template fallback) produced the analysis/recommendation.

`objects` and `sceneDescription` are populated on **every** response regardless of `status` — object/scene recognition runs on every frame independent of the safety-event outcome.

## Setup

### Backend

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

Run it:

```bash
uvicorn app.main:app --reload --port 8000
```

`backend/.env` is loaded automatically on startup (no `--env-file` flag needed) — a real exported environment variable always takes priority over `.env` if both are present. The startup log confirms what's actually enabled:

```
Vision analysis (Gemini): enabled
Groq reasoning: enabled
```

If vision shows `DISABLED`, `/api/analyze` and `/api/analyze-frame` will return `503` until `GEMINI_API_KEY` is set — this is intentional (see [Gemini's role](#geminis-role)), not a bug.

- API root: http://localhost:8000/
- Interactive docs (Swagger UI): http://localhost:8000/docs

A SQLite file (`edgepilot.db`, path configurable via `DATABASE_PATH`) is created next to `backend/` on first run and seeded with demo incidents, so `/api/incidents` returns realistic data immediately even before any real analysis has run.

### Frontend

```bash
npm install
npm run dev
```

The frontend expects the backend at `http://localhost:8000` by default; override with `VITE_API_BASE_URL` (see `.env.example` in the project root).

## Environment variables

Set in `backend/.env` (copy from `backend/.env.example`):

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `GEMINI_API_KEY` | Yes | — | Google Gemini API key for vision analysis. Without it, `/api/analyze*` returns `503`. Get one at https://aistudio.google.com/apikey. |
| `GEMINI_MODEL` | No | `gemini-flash-lite-latest` | Gemini model id. Defaults to a `-latest` alias that auto-tracks Google's current model for this tier; pin a dated model id instead for fully reproducible behavior. |
| `GROQ_API_KEY` | No | — | Groq API key for LLM reasoning. Without it, reasoning falls back to fixed templates automatically. Get one at https://console.groq.com/keys. |
| `GROQ_MODEL` | No | `openai/gpt-oss-120b` | Groq model id used for reasoning. |
| `FRONTEND_ORIGIN` | No | `http://localhost:5173` | Comma-separated list of origins allowed by CORS. |
| `DATABASE_PATH` | No | `./edgepilot.db` | Path to the SQLite database file. |
| `LOG_LEVEL` | No | `INFO` | Python logging level. |
| `LIVE_EVENT_COOLDOWN_SECONDS` | No | `60` | Cooldown window (seconds) before a repeated live event can create another incident. |

Never commit real values for these — `backend/.env` is gitignored; only `backend/.env.example` (with blank/placeholder values) is tracked.

## Testing

Backend:

```bash
cd backend
pytest tests/ -v
```

Frontend:

```bash
npm test           # vitest run
npx tsc -b         # type-check
npm run build      # production build
```

## Project structure

```
Ai_infra_hackthon/
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI app, CORS, .env loading, router registration
│   │   ├── routes/                # analysis, live, incidents, dashboard, analytics(insights), system, health
│   │   ├── services/               # vision (Gemini), llm (Groq), risk, dedup, reasoning, recommendations, frame_extraction
│   │   ├── models/schemas.py      # Pydantic request/response models
│   │   └── database/database.py   # SQLite schema, seed data, queries
│   ├── tests/                     # pytest suite (vision, risk, system, config)
│   ├── requirements.txt
│   └── .env.example
├── src/
│   ├── pages/                     # Dashboard, Analyze, Incidents, Insights (Analytics page), Settings, Landing
│   ├── components/
│   │   ├── dashboard/              # CameraPanel, IncidentCard, MonitoringState, VisionDegradedState, EventTimeline, ...
│   │   ├── incidents/               # IncidentTable, IncidentDetail
│   │   ├── insights/                 # chart components for the Analytics page
│   │   ├── analysis/                 # UploadZone, ProcessingState, AnalysisResultCard
│   │   ├── layout/                   # Sidebar, TopBar, Layout
│   │   └── common/                    # ErrorBoundary, ErrorState, Button, Modal, ...
│   ├── services/api.ts             # All backend HTTP calls
│   ├── data/types.ts               # Shared frontend types (mirrors backend schemas.py)
│   ├── hooks/, utils/              # Small shared helpers (e.g. animated count-up, formatting)
│   └── lazyImport.ts               # Retry-once wrapper for lazy-loaded route chunks
├── .env.example                   # VITE_API_BASE_URL for the frontend
└── README.md
```

## Limitations

- **Prototype, not deployed hardware.** This is a browser-camera monitoring demo, not a production edge-device fleet — see [What this actually is](#what-this-actually-is).
- **Browser/network dependent.** Live monitoring only works while the browser tab is open with camera permission granted, and requires network access to both the backend and Google/Groq's APIs.
- **Third-party API quotas and latency.** Gemini and Groq both have rate limits and can be slow or briefly unavailable; the app surfaces this honestly (Vision Unavailable, template fallback) rather than hiding it.
- **No authentication.** Any client that can reach the API can view, acknowledge, or escalate incidents. Fine for a local demo; not suitable to expose publicly as-is.
- **Local SQLite persistence.** A single file, not a shared or replicated database — fine for a demo, not for multi-instance production use.
- **The human operator is the final decision-maker.** EdgePilot surfaces detections, risk scores, and recommendations — it never takes an automated action in the physical world. Acknowledging or escalating an incident is always a deliberate human step.

## Hackathon demo flow

A suggested walkthrough for a live demo:

1. **Start both servers** (backend on `:8000`, frontend on `:5173`) and open the Dashboard. Point out the live stat cards are real database queries, not hardcoded numbers.
2. **Start the live camera** and show "All Clear" while sitting normally in frame — real Gemini calls are running every ~4 seconds with no incident created, since nothing meaningful is happening.
3. **Trigger a safety event** — e.g. step into a taped-off/marked area, or hold up a sign — and watch the dashboard update in real time: a new incident appears with a risk score, a Groq-written explanation, and a recommended action.
4. **Show the AI reasoning chain** on that incident (detection → context → risk → recommendation) to make the pipeline's logic visible, not a black box.
5. **Acknowledge or escalate** the incident as the human operator, showing the workflow closing the loop.
6. **Switch to Analyze** and upload a photo/video for the one-shot path, showing the same pipeline works outside live monitoring.
7. **Show Incidents and Analytics** for the historical view, and **Settings** to show the system honestly reports what's actually configured (no fake "100% operational" claims).
8. **Optional: force a failure** (e.g. temporarily stop the backend) to show the Vision Unavailable / error states — a good way to demonstrate the system never silently lies about its own state.
