# CityPulse Delhi

Civic reporting that treats **one real-world problem as one incident**. Many citizens reporting the same
pothole produce one incident with many reports, one severity, one owning department and one response
deadline — not forty duplicate complaints nobody can action.

FastAPI + SQLite + React, with **no paid services and no API keys**: maps and place lookup come from
OpenStreetMap, weather from Open-Meteo, and every risk number is computed from data you can inspect.

---

## What is actually live

Everything below reads from the database and from the two free external services. There is no mock data
layer and no placeholder endpoint.

| Capability | How it works |
| --- | --- |
| **Report a problem** | Photo + GPS + description (or coordinates typed by hand). Uploads are stored locally and served back. |
| **Clustering** | Reports within **180 m** of an existing incident whose category and text also agree are folded into it. The match reason and score are returned to the UI, and the radius is served from the API (`/api/meta`) so the UI can never advertise a different number. |
| **Area Intelligence for *any* pincode** | `110043`, `110024`, a locality name like "Lajpat Nagar", or a GPS fix resolves through OpenStreetMap Nominatim — not a hardcoded list. The response names the resolved ward, the source (`live` / `cache` / `offline`) and how old it is. |
| **Risk scoring** | Severity, report volume, corroboration, overdue work and the live 7-day forecast blend into one score with a published band and a confidence percentage. |
| **Response deadlines (SLA)** | Every incident gets a window from its priority. Breaches are surfaced in the UI, on the public scorecard, and swept in the background. |
| **Citizen Credits** | The payout table lives in one place (`backend/app/services/credits.py`) and the API, the UI and the assistant all read from it. Immediate actions pay once per citizen per incident; higher-value claims wait for another human. Credits can never buy priority. |
| **Accountability** | Public scorecard, department league table, per-incident action ledger, and a resolution workflow that requires evidence. |
| **Civic assistant** | A deterministic answer built from live incidents and weather, plus a six-agent trace that reports `COMPLETED` / `PARTIAL` / `SKIPPED` per agent — including an explicit list of what the answer does *not* know. |
| **Auth** | Argon2id password hashing with transparent hash upgrades, JWT sessions, role checks on authority-only routes. |

### Deliberate non-features

The system never claims more than it does. Photo uploads receive a free local screen that recognises
explicit AI-generator markers in filenames or embedded metadata and runs the `umm-maybe/AI-image-detector`
model on image pixels. A score of 10% or higher is routed to human review and applies a -50 credit penalty.
This deliberately sensitive threshold is a probabilistic signal, not proof, and the model is weaker on
ordinary camera photos, so false positives are possible. Photo authenticity
also uses hash reuse and GPS consistency, and the UI says so.
The assistant has no language model;
it assembles sentences from database rows and shows its reasoning so the numbers can be checked.

---

## Quick start (local)

Terminal 1 — API:

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r backend/requirements.txt   # Windows
# .venv/bin/python -m pip install -r backend/requirements.txt     # macOS / Linux
.venv/Scripts/python -m uvicorn app.main:app --reload --app-dir backend
```

Terminal 2 — UI:

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. The API is on <http://localhost:8000> with interactive docs at `/docs`.

No `.env` file is required for local development. To reset the demo data, stop the API and delete
`backend/citypulse.db` plus the contents of `backend/uploads/`.

**Use the virtualenv.** If `pwdlib`/`argon2` are missing, password hashing fails, and a missing dependency
must never be silently absorbed — the app now raises at import rather than quietly changing how passwords
are verified.

## Demo login

| Role | Credentials |
| --- | --- |
| Citizen | `citizen@citypulse.local` / `password123` |
| Authority | `authority@citypulse.local` / `password123` |

The sign-in screen also offers one-click demo buttons. Those are **disabled when `APP_ENV=production`**,
so a public deployment never hands out a token to anyone who presses a button.

---

## Deploy

The whole product is one container: the FastAPI process serves the API, the uploaded evidence and the
built React app.

### Docker Compose (recommended)

```bash
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"   # paste into JWT_SECRET_KEY
docker compose up -d --build
```

Open <http://localhost:8000>. The app answers on `/`, the API docs are at `/docs`, and the health check
is `/health`.

`docker-compose.yml` refuses to start without `JWT_SECRET_KEY`, so the default development secret can
never reach a public deployment.

All mutable state lives on the `citypulse-data` volume (`/data`: SQLite database, uploads, HTTP cache),
so `docker compose down` followed by `up` keeps your data. To wipe it, `docker compose down -v`.

### Docker without Compose

```bash
docker build -t citypulse:latest .
docker run -d --name citypulse -p 8000:8000 \
  -e JWT_SECRET_KEY="$(python -c 'import secrets;print(secrets.token_urlsafe(48))')" \
  -v citypulse-data:/data \
  citypulse:latest
```

### Plain VM / PaaS

```bash
pip install -r backend/requirements.txt
npm ci --prefix frontend && npm run build --prefix frontend
APP_ENV=production JWT_SECRET_KEY=... \
  python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
```

`SERVE_FRONTEND=true` (the default) makes the API serve `frontend/dist`. Set it to `false` if you host the
static build somewhere else, and set `CORS_ORIGINS` to that origin.

### Settings

`.env.example` documents every option. The ones that matter in production:

| Variable | Why |
| --- | --- |
| `JWT_SECRET_KEY` | **Required.** Tokens signed with the default secret can be forged. |
| `APP_ENV=production` | Disables the demo sign-in buttons and logs a loud warning if the secret is still the default. |
| `DATABASE_URL` | Defaults to a SQLite file on the data volume. Any SQLAlchemy URL works. |
| `ENABLE_LIVE_DATA` | OpenStreetMap/Open-Meteo lookups. Turn off for a fully offline instance — the app degrades to cached values and labels them as such. |
| `CITYPULSE_USER_AGENT` | Nominatim requires a descriptive UA with real contact info; placeholder domains get HTTP 403. Set this before public traffic. |
| `CLUSTER_RADIUS_METERS` | Defaults to 180. The UI reads it from the API, so changing it here changes what users are told. |

Respect the OpenStreetMap tile usage policy — do not use the public tile servers for high-volume
production traffic.

---

## Verify

Three levels, all runnable by anyone:

```bash
# 1. Unit + integration suite (62 tests): clustering maths, credit policy,
#    anti-farming, authority checks, SLA clock, area resolution.
.venv/Scripts/python -m unittest discover -s backend/tests -t .

# 2. End-to-end: boots a production-like server against a throwaway database,
#    then drives the real HTTP API (40 checks: seeded logins, clustering,
#    credit payout, arbitrary pincodes, live OSM/Open-Meteo, SPA hosting).
.venv/Scripts/python scripts/smoke_test.py --boot

# 3. Frontend
cd frontend && npm run lint && npm run build
```

`scripts/smoke_test.py` also accepts `--base http://host:port` to check a deployment you already have
running, and `--skip-live` for environments with no internet access. It exits non-zero on failure, so it
can gate a release. GitHub Actions runs all three on every push (`.github/workflows/ci.yml`).

---

## API map

| Area | Endpoints |
| --- | --- |
| Auth | `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`, `GET /api/auth/ledger`, `GET /api/auth/city-scorecard` |
| Reports | `POST /api/posts/` (multipart photo), `POST /api/posts/json`, `GET /api/posts/mine` |
| Incidents | `GET /api/incidents/`, `/{id}`, `/geojson`, `/health`, `/departments`, `/policy`, `/forecasts`, `/scorecard`, `/queue`, `/actions/pending`, `/credits/catalog` |
| Community actions | `POST /api/incidents/{id}/actions`, `POST /api/incidents/{id}/actions/{action_id}/verify`, `POST /api/incidents/{id}/resolve`, `POST /api/incidents/{id}/verify-resolution` |
| Area Intelligence | `GET /api/area/analyze?query=110043` (also `?pincode=` / `?lat=&lon=`), `/resolve`, `/search`, `/summary`, `/monsoon`, `/categories`, `/probe` |
| Assistant | `GET /api/assistant/?q=`, `/agentic`, `/suggestions` |
| System | `GET /health`, `/health/deep`, `/health/live`, `GET /api/meta`, `POST /api/system/cache/clear` |

---

## Layout

```
backend/app/
  config.py            every setting, one place, env-overridable
  api/                 auth, posts, incidents, area, assistant, uploads, system
  services/            intelligence (clustering/SLA/serialisation), area (any-pincode
                       resolution), live (OSM + Open-Meteo with disk cache), credits,
                       accountability, policy, http, storage, clock, migrations, seed
  models/              User, Post, CivicIncident, IncidentReport, CivicAction, CreditTransaction
ai/                    classifier, duplicate matcher, trust engine, risk engine, 6-agent coordinator
frontend/src/
  lib/                 api client, session, data hooks, formatting, toasts
  components/          UI kit, layout, map, incident card, skyline
  pages/               Home, LiveMap, Report, IncidentDetail, AreaIntelligence, CityHealth,
                       AuthorityDashboard, Departments, PolicyLab, Forecasts, CitizenCredits,
                       Activity, Assistant, Profile, Login, Register
scripts/smoke_test.py  black-box verification of a running deployment
```

---

## Known limitations

- **SQLite by default.** Fine for a city pilot and the volume this prototype handles; move to PostgreSQL
  via `DATABASE_URL` before real municipal load.
- **No schema migration tool.** Startup applies additive migrations; destructive changes need a real tool
  such as Alembic.
- **Place lookup is rate-limited by OpenStreetMap.** Heavy traffic needs your own Nominatim instance or a
  commercial geocoder; responses are disk-cached to soften this.
- **No email/SMS.** Deadlines are visible in the app and on the scorecard, but nothing notifies a citizen
  out of band.
- **Photo authenticity is heuristic.** Hash reuse and GPS consistency, not image content analysis.
