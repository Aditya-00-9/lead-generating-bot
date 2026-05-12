import os
import sys
from pathlib import Path
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

# Ensure project root is importable for `app.*` modules.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.db.base import Base
from app.models.lead import Lead  # noqa: F401
from app.utils.postgres_url import normalize_postgres_url

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _migration_url() -> str:
    url = (os.getenv("SYNC_DATABASE_URL") or os.getenv("DATABASE_URL") or "").strip()
    if not url:
        url = (config.get_main_option("sqlalchemy.url") or "").strip()
    return normalize_postgres_url(url)


def run_migrations_offline() -> None:
    url = _migration_url()
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Use create_engine + explicit URL so we never rely on engine_from_config
    # merging alembic.ini (bare postgresql:// can imply psycopg2).
    connectable = create_engine(_migration_url(), poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
