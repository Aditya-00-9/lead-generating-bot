from app.utils.postgres_url import normalize_postgres_url


def test_normalize_bare_postgresql_to_psycopg3() -> None:
    u = normalize_postgres_url("postgresql://u:p@host/db")
    assert u.startswith("postgresql+psycopg://")


def test_normalize_strips_channel_binding() -> None:
    u = normalize_postgres_url(
        "postgresql://u:p@host/db?sslmode=require&channel_binding=require"
    )
    assert "channel_binding" not in u
    assert "sslmode=require" in u
