# KramaAI Lead Monitoring Platform

Production-grade AI lead-intelligence pipeline for competitor dissatisfaction monitoring, scoring, and outbound assistance.

## Architecture

Daily flow:

1. Scheduler (`Cron`, GitHub Actions, or APScheduler)
2. Source collectors: **`OpenAI Web Research`** when `OPENAI_API_KEY` is set (on by default; disable with `ENABLE_OPENAI_WEB_RESEARCH=false`), optional **`OpenAI URL scrape`**, then **`Reddit`** and **`Google Alerts RSS`** only when those credentials or real feed URLs are configured; optional demo placeholders if `ENABLE_PLACEHOLDER_SOURCES=true`
3. Normalization + sanitization
4. Deduplication (URL + content hash + fuzzy match window)
5. **OpenAI enrichment** (second pass: structured **classification**, scores, suggested reply — `OpenAIEnricher`)
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

**Minimum to run ingestion:** `DATABASE_URL`, `OPENAI_API_KEY`, and `KEYWORDS`. With only those, the pipeline uses **OpenAI web discovery** (no Reddit or Google setup required).

Also set `SLACK_WEBHOOK_URL` if you want the daily digest.

Optional:
- **`ENABLE_OPENAI_WEB_RESEARCH=false`** — turn off web search discovery (saves API cost).
- **`OPENAI_SCRAPER_URLS`** — comma-separated **https** pages; OpenAI extracts lead-like snippets from page text.
- **`OPENAI_RESPONSES_MODEL`**, **`OPENAI_COLLECTION_MODEL`**, **`OPENAI_COLLECTION_MIN_RELEVANCE`** — tune collection models and relevance cutoff.
- **`REDDIT_CLIENT_ID`** / **`REDDIT_CLIENT_SECRET`** — adds Reddit collection when both are set.
- **`GOOGLE_ALERT_RSS_URLS`** — comma-separated real Google Alert RSS feed URLs (template `feeds/0000/...` URLs are ignored).
- **`ENABLE_PLACEHOLDER_SOURCES=true`** — demo-only placeholder sources.
- **`SENTRY_DSN`**, **`SYNC_DATABASE_URL`** (Alembic; often same as `DATABASE_URL` with sync driver)

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
make run
# or: python -m app.scheduler.runner
```

This run now also:
- creates a per-run Excel report in `reports/new_leads_YYYY-MM-DD.xlsx`
- refreshes a master Excel report in `reports/all_leads_master.xlsx` (historical leads)
- writes report rows to Postgres table `lead_reports` with columns:
  `Date | Source | Link | Competitor | Pain Point | Intent | Suggested Reply | Status`
- both Excel reports include visibility columns for workflow follow-up:
  `Run Date | Captured At | ... | Status | Reviewed By | Reviewed At | Posted At`
- posts daily digest to Slack webhook
- optionally uploads both Excel files to Slack when `SLACK_BOT_TOKEN` and `SLACK_CHANNEL_ID` are set

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

**Required** repository secrets for the daily job: `DATABASE_URL`, `OPENAI_API_KEY`, `KEYWORDS`, and `SLACK_WEBHOOK_URL` (if you want Slack). Set `OPENAI_MODEL` if you use a non-default model.

**Optional:** `GOOGLE_ALERT_RSS_URLS`, `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `SYNC_DATABASE_URL`, and others from `.env.example`. Empty optional secrets are fine; Reddit and Google collectors are skipped when not configured.

### Turn on the GitHub cron (one-time)

The schedule is **already in the repo** (`daily-ingestion.yml`, `0 14 * * *` UTC). GitHub runs it only after this is done:

1. **Enable Actions:** Repo → **Settings** → **Actions** → **General** → under *Actions permissions*, allow actions (default for public repos is fine).
2. **Add secrets:** **Settings** → **Secrets and variables** → **Actions** → **New repository secret** for each name in the list above. `DATABASE_URL` must be a **publicly reachable Postgres** URL (not `localhost` on your PC).
3. **Confirm the workflow exists:** **Actions** → left sidebar **Daily lead ingestion** (if the tab is empty, push any commit to `main` or wait a minute after enabling Actions).
4. **Test without waiting for 14:00 UTC:** open **Daily lead ingestion** → **Run workflow** → branch `main` → **Run workflow**.

Until secrets are set, the workflow fails fast on the first step with an error pointing at `DATABASE_URL`.

The **Run lead monitor** step sets **`APP_ENV=production`** so ingestion validates **`OPENAI_API_KEY`** and **`KEYWORDS`** before work starts. Optional **`STRICT_STARTUP_VALIDATION=true`** (in `.env` or GitHub secrets) tightens API boot and ingestion (e.g. Reddit / Google URLs in strict mode).

**Health:** **`GET /health`** liveness; **`GET /ready`** checks PostgreSQL (`SELECT 1`). Docker image runs as **non-root** (`appuser`) and includes a **HEALTHCHECK** on `/health`.

## Deploy (Vercel + cron)

1. Create a Vercel project from this repo. The FastAPI entrypoint is set in `pyproject.toml` as `app.main:app`.
2. In Vercel **Environment variables**, add the same values you use locally (`DATABASE_URL`, `OPENAI_API_KEY`, `KEYWORDS`, Slack, Reddit, etc.). Set **`CRON_SECRET`** to a long random string; Vercel Cron will send `Authorization: Bearer <CRON_SECRET>` to your job route.
3. `vercel.json` schedules **GET** `/api/cron/daily-ingestion` daily at **14:00 UTC** (same as the GitHub workflow, **7:30 PM IST**). That route runs the full ingestion pipeline (Slack digest, DB writes, Excel under `/tmp/reports` when `VERCEL` is set).
4. **Limits:** Vercel Functions have a **maximum duration** (short on Hobby). Ingestion can exceed that if you collect many items or call OpenAI heavily. For a reliable daily job without time limits, prefer **GitHub Actions** (`daily-ingestion.yml`) or a VM / Docker scheduler. You can still host the **read API** on Vercel and run the heavy job only on GitHub.

## Troubleshooting

- `ModuleNotFoundError`: ensure virtual environment is active.
- DB connection errors: verify `DATABASE_URL` and Postgres availability.
- **`Name or service not known` with `neon. tech` in the error:** your connection string has a **space** in the hostname (`neon. tech` instead of `neon.tech`). Fix the **GitHub secret** (and local `.env`) by re-copying from Neon with no spaces. The app also **auto-corrects** that typo when normalizing URLs, but fixing the secret is still best.
- Empty digests: verify `KEYWORDS` and `OPENAI_API_KEY`; add Reddit or real Google Alert feeds only if you rely on those sources.
- OpenAI validation failures: inspect logs for malformed model output and retry behavior.

## Scaling Recommendations

- Add Celery/RQ worker pool for enrichment fan-out at high volume.
- Batch API calls and include back-pressure controls per collector.
- Add Redis cache for short-term dedupe candidate sets.
- Add partitioning/index tuning as daily volume grows.
- Extend to multi-tenant schema with org-level source and model configs.
