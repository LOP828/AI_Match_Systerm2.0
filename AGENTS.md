# Repository Guidelines

## Project Structure & Module Organization
This repository is split into `backend/` and `frontend/`. Backend application code lives in `backend/app/`: `api/` for FastAPI routes, `services/` for business logic, `models/` for SQLAlchemy models, and `schemas/` for request/response types. Database migrations live in `backend/alembic/versions/`, tests in `backend/tests/`, and utility scripts in `backend/scripts/`. Frontend code lives in `frontend/src/`: `pages/` for route-level screens, `auth/` for session state, `api/` for the client layer, and `test/` for shared test setup. Keep the root `.venv/` for local Python tooling.

## Build, Test, and Development Commands
Run backend commands from `backend/`:

- `pip install -r requirements.txt` installs FastAPI, SQLAlchemy, Alembic, and test dependencies.
- `alembic upgrade head` applies the current schema.
- `uvicorn app.main:app --reload` starts the API on `localhost:8000`.
- `pytest` runs the backend suite.
- `python scripts/postgres_smoke_test.py --database-url postgresql+psycopg://...` validates migrations against PostgreSQL.

Run frontend commands from `frontend/`:

- `npm install` installs Vite, React 19, Vitest, and lint tooling.
- `npm run dev` starts the Vite app on `localhost:5173`.
- `npm run build` runs TypeScript compile plus production build.
- `npm run test` runs Vitest once.
- `npm run lint` runs ESLint.

## Coding Style & Naming Conventions
Python follows PEP 8: 4-space indentation, `snake_case` for modules/functions, and `PascalCase` for models and schema classes. Keep endpoint wiring in `api/` and reusable domain logic in `services/`. TypeScript/React uses 2-space indentation, `PascalCase` component files such as `LoginPage.tsx`, and `camelCase` helpers/hooks. Favor descriptive Tailwind utility groupings over inline style objects.

## Testing Guidelines
Backend tests use Pytest with temporary SQLite fixtures from `backend/tests/conftest.py`; name files `test_*.py`. Frontend tests use Vitest + Testing Library in `jsdom`, with shared cleanup in `frontend/src/test/setup.ts`; name files `*.test.tsx`. No coverage threshold is configured, so add focused tests for each changed API flow, service rule, or user-facing page behavior.

## Commit & Pull Request Guidelines
Local history uses Conventional Commit prefixes such as `feat:`, `docs:`, and `chore:` with short imperative summaries. Keep PRs focused, note schema or `.env` changes, link the relevant issue, and list the commands you ran to verify the change. Include screenshots for UI updates under `frontend/src/pages/`.

## Security & Configuration Tips
Copy `backend/.env.example` to `backend/.env` for local setup. Never commit secrets such as `JWT_SECRET_KEY` or `DEEPSEEK_API_KEY`. SQLite is the default local database; run the PostgreSQL smoke test before shipping migration-heavy changes.
