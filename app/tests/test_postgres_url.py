from app.utils.postgres_url import normalize_postgres_url


def test_normalize_bare_postgresql_to_psycopg3() -> None:
    u = normalize_postgres_url("postgresql://u:p@host/db")
    assert u.startswith("postgresql+psycopg://")


def test_normalize_fixes_neon_host_typo_space_before_tech() -> None:
    broken = "postgresql://u:p@ep-x-pooler.c-8.us-east-1.aws.neon. tech/db?sslmode=require"
    fixed = normalize_postgres_url(broken)
    assert "neon. tech" not in fixed
    assert "neon.tech" in fixed


def test_normalize_strips_channel_binding() -> None:
    u = normalize_postgres_url(
        "postgresql://u:p@host/db?sslmode=require&channel_binding=require"
    )
    assert "channel_binding" not in u
    assert "sslmode=require" in u
