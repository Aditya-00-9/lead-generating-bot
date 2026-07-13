install:
	pip install -r requirements.txt

run-api:
	python scripts/run_api.py

run-pipeline:
	python -m app.scheduler.runner

run: run-pipeline

run-local:
	powershell -ExecutionPolicy Bypass -File scripts/run_local.ps1

migrate:
	alembic upgrade head

test:
	pytest -q --cov=app --cov-report=term-missing
