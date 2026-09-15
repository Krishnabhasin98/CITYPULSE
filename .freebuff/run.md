# Running CityPulse in a preview thread

CityPulse is two things in one repository: a FastAPI backend (`backend/`, which also imports the `ai/`
package from the repo root) and a React/Vite frontend (`frontend/`). The backend can serve the built
frontend itself, and that is the mode used for previews here, because it is a single process with no proxy
and no CORS to get wrong.

## 1. Reproduce the artifacts a fresh checkout needs

Python dependencies live in a virtualenv that **is** committed to this working copy (`.venv/`, deliberately
gitignored). If it is missing:

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r backend/requirements.txt
```

`pwdlib`/`argon2` must be present. The backend now raises at import instead of silently falling back to a
weaker hashing scheme, so a missing virtualenv surfaces immediately as a startup error.

Frontend dependencies and the production bundle:

```bash
cd frontend && npm install && npm run build
```

`frontend/dist/` must exist for a preview: the backend serves that bundle. Rebuild it after any change
under `frontend/src/`, since the backend serves static files from disk and does not watch them.

Configuration: `backend/.env` is optional and, if present, is loaded automatically. Copy it from the main
checkout rather than recreating it — **do not** commit or paste its values. With no `.env` at all the app
still runs on local SQLite with live OpenStreetMap/Open-Meteo data and no API keys.

Database: `backend/citypulse.db` is created on first start. A legacy `citypulse.db` in the repo root is
adopted automatically, which is what preserves the seeded Delhi demo data (5 incidents, one of them a
clustered duplicate pair). Startup also applies additive migrations — that is expected, not an error.

## 2. How to run the server

Port **8100** is used for previews because 8000 is normally occupied by a manually-started development
server and the frontend dev port 5173 is left free for `npm run dev`. The server serves the API, the
uploaded evidence (`/uploads`) and the built SPA on one origin.

Start it **detached** (Windows — `Start-Process` with a hidden window and separate stdout/stderr files,
which must be different paths or PowerShell fails):

```bash
powershell -NoProfile -Command "(Start-Process -FilePath 'C:\Users\lenovo\Desktop\HACKVIPS\CityPulse\.venv\Scripts\python.exe' -ArgumentList '-m','uvicorn','app.main:app','--app-dir','backend','--host','127.0.0.1','--port','8100' -RedirectStandardOutput '<log>' -RedirectStandardError '<log>.err' -WorkingDirectory 'C:\Users\lenovo\Desktop\HACKVIPS\CityPulse' -WindowStyle Hidden -PassThru).Id"
```

Name the executable exactly (`python.exe`, `npm.cmd`) — `Start-Process` does not resolve shell shims. The
call returns the pid; confirm the process survived and the URL answers before registering the preview:

```bash
powershell -NoProfile -Command "Get-Process -Id <pid>"
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8100/health
```

Then register `http://127.0.0.1:8100` with that pid. Uvicorn reads files from disk per request, so a
frontend rebuild is picked up without a restart; only backend Python changes need one.

To restart: find the listener with
`netstat -ano | grep LISTENING | grep ":8100"`, then `taskkill //PID <pid> //F`.

Note that `uvicorn` under this shell may keep the invoking shell waiting even when launched via
`Start-Process`; the process does still start and survive. Verify by port/health rather than by the
command returning.

## Verifying the running preview

```bash
.venv/Scripts/python -m unittest discover -s backend/tests -t .   # 62 backend tests
.venv/Scripts/python scripts/smoke_test.py --boot                 # 43 end-to-end HTTP checks
.venv/Scripts/python scripts/smoke_test.py --base http://127.0.0.1:8100
```

The smoke test is the fast way to check a preview: it asserts seeded logins, clustering, credit payout and
anti-farming, authority-only routes, arbitrary pincode resolution, live OSM/Open-Meteo reachability, and
that no client page route is shadowed by an API path (which `/health` once was).

Demo accounts: `citizen@citypulse.local` / `password123` and `authority@citypulse.local` / `password123`.
One-click demo sign-in is disabled when `APP_ENV=production`; previews run in `development`, so the
buttons work.
