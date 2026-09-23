# KramaAI Lead Monitoring Platform

> Production-grade AI lead-intelligence pipeline for competitor dissatisfaction monitoring, scoring, and outbound assistance.

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-teal?logo=fastapi)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue?logo=postgresql)
![OpenAI](https://img.shields.io/badge/OpenAI-API-black?logo=openai)
![Slack](https://img.shields.io/badge/Slack-Block_Kit-4A154B?logo=slack)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker)
![CI](https://img.shields.io/badge/CI-GitHub_Actions-2088FF?logo=github-actions)
![Tests](https://img.shields.io/badge/Tests-pytest-green?logo=pytest)

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Repository Structure](#repository-structure)
- [Getting Started](#getting-started)
- [Database Migrations](#database-migrations)
- [Running](#running)
- [Docker](#docker)
- [Testing](#testing)
- [CI/CD](#cicd)
- [Deployment (Vercel + Cron)](#deploy-vercel--cron)
- [Troubleshooting](#troubleshooting)
- [Scaling Recommendations](#scaling-recommendations)

## Overview

A daily pipeline that collects competitor dissatisfaction signals from web sources, enriches them with OpenAI, deduplicates, scores, and ranks leads, then publishes a Slack digest and Excel reports for human review.

## Architecture

Daily flow:

1. Scheduler (`Cron`, GitHub Actions, or APScheduler)
2. Source collectors: **OpenAI Web Research** when `OPENAI_API_KEY` is set (on by default; disable with `ENABLE_OPENAI_WEB_RESEARCH=false`), optional **OpenAI URL scrape**, then **Reddit** and **Google Alerts RSS** only when those credentials or real feed URLs are configured; optional demo placeholders if `ENABLE_PLACEHOLDER_SOURCES=true`
3. Normalization + sanitization
4. Deduplication (URL + content hash + fuzzy match window)
5. **OpenAI enrichment** (second pass: structured classification, scores, suggested reply — `OpenAIEnricher`)
6. Lead ranking and persistence (`PostgreSQL + SQLAlchemy`)
7. Slack digest (`Block Kit`, grouped by intent and competitor)
8. Human review and manual posting

## Features

- **Multi-source collection** — OpenAI web discovery, URL scraping, Reddit, Google Alerts RSS
- **AI enrichment** — Structured classification, intent scoring, and suggested reply generation via OpenAI
- **Smart deduplication** — URL + content hash + fuzzy match window
- **Lead ranking** — Scoring and persistence to PostgreSQL
- **Slack digest** — Block Kit formatted, grouped by intent and competitor
- **Excel reports** — Per-run and master reports with workflow tracking columns
- **API** — FastAPI endpoints for lead browsing, stats, reclassification, and reply generation
- **Health checks** — `/health` liveness and `/ready` PostgreSQL readiness probes
- **Non-root Docker** — Container runs as `appuser` with built-in HEALTHCHECK

## Repository Structure

| Directory | Description |
|-----------|-------------|
| `app/api` | FastAPI routes (`/leads`, `/leads/{id}`, `/stats`, `/reclassify`, `/generate-reply`) |
| `app/collectors` | Source adapters |
| `app/classifiers` | OpenAI enrichment logic |
| `app/dedupe` | Duplicate detection engine |
| `app/ranking` | Lead scoring |
| `app/storage` | Repository layer |
| `app/slack` | Block Kit digest publishing |
| `app/scheduler` | Ingestion runners |
| `app/db` + `app/models` | SQLAlchemy models/session |
| `alembic` | Migration config and versions |
| `app/tests` | Unit/integration-ready tests |

## Getting Started

### Local Setup

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
copy .env.example .env   # Windows
# cp .env.example .env    # Linux/Mac
```

**Minimum to run ingestion:** `DATABASE_URL`, `OPENAI_API_KEY`, and `KEYWORDS`. With only those, the pipeline uses OpenAI web discovery (no Reddit or Google setup required).

Also set `SLACK_WEBHOOK_URL` if you want the daily digest.

### Optional Configuration

| Variable | Description |
|----------|-------------|
| `ENABLE_OPENAI_WEB_RESEARCH` | Set to `false` to turn off web search discovery (saves API cost) |
| `OPENAI_SCRAPER_URLS` | Comma-separated https pages; OpenAI extracts lead-like snippets |
| `OPENAI_RESPONSES_MODEL` | Tune the enrichment model |
| `OPENAI_COLLECTION_MODEL` | Tune the collection model |
| `OPENAI_COLLECTION_MIN_RELEVANCE` | Relevance cutoff for collection |
| `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` | Adds Reddit collection when both are set |
| `GOOGLE_ALERT_RSS_URLS` | Comma-separated real Google Alert RSS feed URLs |
| `ENABLE_PLACEHOLDER_SOURCES` | Set to `true` for demo-only placeholder sources |
| `SENTRY_DSN` | Sentry error tracking |
| `SYNC_DATABASE_URL` | Alembic sync URL (often same as `DATABASE_URL` with sync driver) |

## Database Migrations

```bash
alembic upgrade head
```

## Running

### API Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Daily Pipeline (once)

```bash
make run
# or: python -m app.scheduler.runner
```

This run also:
- Creates a per-run Excel report in `reports/new_leads_YYYY-MM-DD.xlsx`
- Refreshes a master Excel report in `reports/all_leads_master.xlsx` (historical leads)
- Writes report rows to Postgres table `lead_reports` with columns: `Date | Source | Link | Competitor | Pain Point | Intent | Suggested Reply | Status`
- Both Excel reports include visibility columns: `Run Date | Captured At | ... | Status | Reviewed By | Reviewed At | Posted At`
- Posts daily digest to Slack webhook
- Optionally uploads both Excel files to Slack when `SLACK_BOT_TOKEN` and `SLACK_CHANNEL_ID` are set

### APScheduler (long-running)

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

GitHub Actions workflows:

- `.github/workflows/ci.yml` — Runs tests on push and pull requests to `main` / `master`
- `.github/workflows/daily-ingestion.yml` — Runs `alembic upgrade head` then `python -m app.scheduler.runner` on a schedule (`0 14 * * *` UTC = 7:30 PM IST) and on manual `workflow_dispatch`

### Required Repository Secrets

| Secret | Required |
|--------|----------|
| `DATABASE_URL` | Yes (publicly reachable Postgres) |
| `OPENAI_API_KEY` | Yes |
| `KEYWORDS` | Yes |
| `SLACK_WEBHOOK_URL` | For Slack digest |
| `OPENAI_MODEL` | If using non-default model |

Optional: `GOOGLE_ALERT_RSS_URLS`, `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `SYNC_DATABASE_URL`, and others from `.env.example`.

### Enabling the GitHub Cron

1. **Enable Actions:** Repo → Settings → Actions → General → allow actions
2. **Add secrets:** Settings → Secrets and variables → Actions → New repository secret
3. **Confirm workflow:** Actions → Daily lead ingestion (push any commit to `main` if tab is empty)
4. **Test:** Daily lead ingestion → Run workflow → branch `main` → Run workflow

The **Run lead monitor** step sets `APP_ENV=production` so ingestion validates `OPENAI_API_KEY` and `KEYWORDS` before work starts. Optional `STRICT_STARTUP_VALIDATION=true` tightens API boot and ingestion.

**Health:** `GET /health` liveness; `GET /ready` checks PostgreSQL (`SELECT 1`).

## Deploy (Vercel + Cron)

1. Create a Vercel project from this repo. The FastAPI entrypoint is set in `pyproject.toml` as `app.main:app`.
2. In Vercel Environment variables, add the same values as local (`DATABASE_URL`, `OPENAI_API_KEY`, `KEYWORDS`, Slack, Reddit, etc.). Set `CRON_SECRET` to a long random string.
3. `vercel.json` schedules `GET /api/cron/daily-ingestion` daily at 14:00 UTC (7:30 PM IST). That route runs the full ingestion pipeline.
4. **Limits:** Vercel Functions have a maximum duration (short on Hobby). For reliable daily jobs, prefer GitHub Actions or a VM/Docker scheduler. You can host the read API on Vercel and run the heavy job on GitHub.

## Troubleshooting

- `ModuleNotFoundError`: ensure virtual environment is active
- DB connection errors: verify `DATABASE_URL` and Postgres availability
- `Name or service not known` with `neon. tech`: connection string has a space in the hostname — fix the GitHub secret and local `.env`
- Empty digests: verify `KEYWORDS` and `OPENAI_API_KEY`; add Reddit or Google Alert feeds only if needed
- OpenAI validation failures: inspect logs for malformed model output and retry behavior

## Scaling Recommendations

- Add Celery/RQ worker pool for enrichment fan-out at high volume
- Batch API calls and include back-pressure controls per collector
- Add Redis cache for short-term dedupe candidate sets
- Add partitioning/index tuning as daily volume grows
- Extend to multi-tenant schema with org-level source and model configs
