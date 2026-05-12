# KramaAI Lead Monitoring Platform

Production-grade AI lead-intelligence pipeline for competitor dissatisfaction monitoring, scoring, and outbound assistance.

## Architecture

Daily flow:

1. Scheduler (`Cron`, GitHub Actions, or APScheduler)
2. Source collectors (`Reddit API`, `Google Alerts RSS`, plug-in placeholders for `G2`, `Capterra`, `App Store`, `Play Store`)
3. Normalization + sanitization
4. Deduplication (URL + content hash + fuzzy match window)
5. OpenAI enrichment (JSON-structured outputs)
6. Lead ranking and persistence (`PostgreSQL + SQLAlchemy`)
7. Slack digest (`Block Kit`, grouped by intent and competitor)
8. Human review and manual posting

## Repository Structure

- `app/api`: FastAPI routes (`/leads`, `/leads/{id}`, `/stats`, `/reclassify`, `/generate-reply`)
- `app/collectors`: source adapters
- `app/classifiers`: OpenAI enrichment logic
- `app/dedupe`: duplicate detection engine
- `app/ranking`: lead scoring
- `app/storage`: repository layer
- `app/slack`: Block Kit digest publishing
- `app/scheduler`: ingestion runners
- `app/db` + `app/models`: SQLAlchemy models/session
- `alembic`: migration config and versions
- `app/tests`: unit/integration-ready tests

## Setup (Local)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Update `.env` with:
- `OPENAI_API_KEY`
- `DATABASE_URL` and `SYNC_DATABASE_URL`
- `SLACK_WEBHOOK_URL`
- `KEYWORDS`
- `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`
- optional: `GOOGLE_ALERT_RSS_URLS`, `SENTRY_DSN`

## Database Migrations

```bash
alembic upgrade head
```

## Run

API:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Daily pipeline once:

```bash
python -m app.scheduler.runner
```

This run now also:
- creates an Excel report in `reports/lead_report_YYYY-MM-DD.xlsx`
- writes report rows to Postgres table `lead_reports` with columns:
  `Date | Source | Link | Competitor | Pain Point | Intent | Suggested Reply | Status`
- posts daily digest to Slack webhook
- optionally uploads the Excel file to Slack when `SLACK_BOT_TOKEN` and `SLACK_CHANNEL_ID` are set

APScheduler (long-running):

```bash
python -m app.scheduler.apscheduler_job
```

## Docker

```bash
docker compose up --build
```

## Testing

```bash
pytest -q --cov=app --cov-report=term-missing
```

## CI/CD

GitHub Actions:

- `.github/workflows/ci.yml` — runs tests on push and pull requests to `main` / `master`.
- `.github/workflows/daily-ingestion.yml` — runs `alembic upgrade head` then `python -m app.scheduler.runner` on a schedule (`0 14 * * *` UTC = **7:30 PM IST**) and on manual **workflow_dispatch**.

Use a **hosted Postgres** (Neon, Supabase, RDS, etc.): set `DATABASE_URL` in repository secrets to the connection string the app uses. Optional `SYNC_DATABASE_URL` if you keep a separate sync URL for Alembic; otherwise the workflow derives a sync URL from `DATABASE_URL` (including `+asyncpg` → `+psycopg` for the migrate step).

Required repository secrets for the daily job:

- `OPENAI_API_KEY`, `OPENAI_MODEL`, `SLACK_WEBHOOK_URL`, `DATABASE_URL`, `KEYWORDS`, `GOOGLE_ALERT_RSS_URLS`, `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`

## Deploy (Vercel + cron)

1. Create a Vercel project from this repo. The FastAPI entrypoint is set in `pyproject.toml` as `app.main:app`.
2. In Vercel **Environment variables**, add the same values you use locally (`DATABASE_URL`, `OPENAI_API_KEY`, `KEYWORDS`, Slack, Reddit, etc.). Set **`CRON_SECRET`** to a long random string; Vercel Cron will send `Authorization: Bearer <CRON_SECRET>` to your job route.
3. `vercel.json` schedules **GET** `/api/cron/daily-ingestion` daily at **14:00 UTC** (same as the GitHub workflow, **7:30 PM IST**). That route runs the full ingestion pipeline (Slack digest, DB writes, Excel under `/tmp/reports` when `VERCEL` is set).
4. **Limits:** Vercel Functions have a **maximum duration** (short on Hobby). Ingestion can exceed that if you collect many items or call OpenAI heavily. For a reliable daily job without time limits, prefer **GitHub Actions** (`daily-ingestion.yml`) or a VM / Docker scheduler. You can still host the **read API** on Vercel and run the heavy job only on GitHub.

## Troubleshooting

- `ModuleNotFoundError`: ensure virtual environment is active.
- DB connection errors: verify `DATABASE_URL` and Postgres availability.
- Empty digests: verify `KEYWORDS`, Reddit credentials, and Google Alert feed URLs.
- OpenAI validation failures: inspect logs for malformed model output and retry behavior.

## Scaling Recommendations

- Add Celery/RQ worker pool for enrichment fan-out at high volume.
- Batch API calls and include back-pressure controls per collector.
- Add Redis cache for short-term dedupe candidate sets.
- Add partitioning/index tuning as daily volume grows.
- Extend to multi-tenant schema with org-level source and model configs.
