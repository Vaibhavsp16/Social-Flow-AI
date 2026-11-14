"""The database URL must always resolve to a driver that is actually installed.

A hosted Postgres provider hands out a bare ``postgresql://`` string. SQLAlchemy 2.1 maps that to
the psycopg (v3) dialect, but requirements.txt installs psycopg2-binary, so the container died at
import with ``ModuleNotFoundError: No module named 'psycopg'`` before opening a connection. These
tests pin the normalisation so a deploy cannot silently reintroduce it.
"""

import pytest
from sqlalchemy import create_engine

from app.core.config import _pin_psycopg2

NEON = (
    "postgresql://neondb_owner:pw@ep-hidden-sky-123-pooler.eu-central-1.aws.neon.tech/neondb"
    "?sslmode=require&channel_binding=require"
)


def test_bare_postgresql_scheme_is_pinned_to_psycopg2():
    url = _pin_psycopg2(NEON)
    assert url.startswith("postgresql+psycopg2://")
    # Only the prefix changes; credentials, host and query string must survive untouched.
    assert url.endswith("@ep-hidden-sky-123-pooler.eu-central-1.aws.neon.tech/neondb"
                       "?sslmode=require&channel_binding=require")
    assert "neondb_owner:pw@" in url


def test_postgres_alias_is_pinned_too():
    # Heroku and Supabase still hand out postgres://
    assert _pin_psycopg2("postgres://u:p@host:5432/db").startswith("postgresql+psycopg2://")


def test_explicit_driver_is_left_alone():
    already = "postgresql+psycopg2://u:p@host/db"
    assert _pin_psycopg2(already) == already


def test_surrounding_quotes_and_whitespace_are_stripped():
    # A pasted value in a hosting dashboard is easily wrapped in quotes.
    assert _pin_psycopg2(f'  "{NEON}"  ').startswith("postgresql+psycopg2://")


def test_sqlite_url_is_untouched():
    assert _pin_psycopg2("sqlite:///./local.db") == "sqlite:///./local.db"


@pytest.mark.parametrize("raw", [NEON, "postgres://u:p@host:5432/db"])
def test_normalised_url_resolves_to_the_installed_driver(raw):
    engine = create_engine(_pin_psycopg2(raw))
    assert engine.dialect.driver == "psycopg2"
    assert engine.dialect.dbapi.__name__ == "psycopg2"
