install:
	pip install -r requirements.txt

run-api:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run-pipeline:
	python -m app.scheduler.runner

migrate:
	alembic upgrade head

test:
	pytest -q --cov=app --cov-report=term-missing
