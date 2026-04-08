# Repository Guidelines

## Project Structure & Module Organization
`backend/` contains the FastAPI app, research pipeline, SQLAlchemy models, and Alembic migrations. Main code lives under `backend/app/`; add schema or workflow changes near `api/`, `db/`, and `research/`. `backend/tests/` covers API, provider, and service behavior with `pytest`. `frontend/` is the Vue 3 + Vite client: keep views in `frontend/src/views/`, shared API/SSE code in `frontend/src/services/`, Pinia stores in `frontend/src/stores/`, and types in `frontend/src/types/`. Use `lib/deep-research/` as a read-only reference unless you are intentionally syncing with the upstream example.

## Build, Test, and Development Commands
From the repo root, `docker compose up --build` starts PostgreSQL, the API, and the Vite frontend. Backend local setup uses `cd backend && uv sync`, `uv run alembic upgrade head`, and `uv run uvicorn app.main:app --reload`. Frontend local setup uses `cd frontend && npm install`, `npm run dev`, and `npm run build`. Run backend tests with `cd backend && uv run pytest`, frontend unit tests with `cd frontend && npm test`, and browser tests with `cd frontend && npm run test:e2e`.

## Coding Style & Naming Conventions
Python follows PEP 8 with 4-space indentation and a configured Ruff line length of 100; keep modules snake_case and prefer explicit, typed function signatures. Frontend code uses TypeScript, 2-space indentation, semicolons, and double quotes. Name Vue views/components in PascalCase (`HomeView.vue`), stores and services in camelCase file groups (`research.ts`, `api.ts`), and keep shared types under `src/types/`.

## Testing Guidelines
Add backend tests beside related behavior in `backend/tests/test_*.py`. Frontend unit tests live in `frontend/tests/unit/*.test.ts`; Playwright flows live in `frontend/tests/e2e/*.spec.ts`. Cover new API branches, persisted task behavior, and SSE/report rendering paths when changing research flow or state handling. No coverage threshold is enforced yet, so treat regression coverage as part of each change.

## Commit & Pull Request Guidelines
Current history is minimal (`init`), so prefer short imperative commit subjects with scope, for example `backend: add follow-up task fields` or `frontend: handle SSE retry metadata`. Keep commits focused. PRs should explain user-visible behavior, list config or migration changes, link the issue, and include screenshots for UI changes or sample request/response snippets for API updates.

## Security & Configuration Tips
Copy `.env.example` to `.env` for local setup and never commit secrets. Treat `API_BEARER_TOKEN`, model API keys, and database URLs as required local configuration. When changing settings or provider options, update `.env.example` and the relevant README section in the same PR.
