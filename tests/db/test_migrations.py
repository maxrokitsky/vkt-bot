"""Smoke-тест миграций Alembic.

Прогоняется только на настоящем PostgreSQL: миграции пишутся под него, а
``ALEMBIC_DB_URL`` позволяет направить их на отдельную тестовую базу.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import uuid

import pytest
import sqlalchemy as sa

from vkt_bot.db.base import Model

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.postgres


@pytest.fixture
def migration_db_url(db_url: str, is_postgres: bool) -> str:
    """Отдельная пустая база под миграции."""
    if not is_postgres:
        pytest.skip("Миграции прогоняются только на PostgreSQL")

    base = sa.engine.make_url(db_url).set(drivername="postgresql+psycopg")
    name = f"vkt_migrations_{uuid.uuid4().hex[:8]}"
    admin = sa.create_engine(
        base.set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    with admin.connect() as conn:
        conn.execute(sa.text(f'CREATE DATABASE "{name}"'))
    try:
        yield str(base.set(database=name))
    finally:
        with admin.connect() as conn:
            conn.execute(
                sa.text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :name"
                ),
                {"name": name},
            )
            conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{name}"'))
        admin.dispose()


def run_alembic(url: str, *args: str) -> subprocess.CompletedProcess[str]:
    """Запустить alembic на указанной базе."""
    env = {**os.environ, "ALEMBIC_DB_URL": url}
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "alembic", *args],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_upgrade_head_on_clean_database(migration_db_url: str) -> None:
    """``alembic upgrade head`` проходит на пустой базе."""
    result = run_alembic(migration_db_url, "upgrade", "head")
    assert result.returncode == 0, result.stderr


def test_schema_matches_models(migration_db_url: str) -> None:
    """После миграций все таблицы моделей существуют."""
    assert run_alembic(migration_db_url, "upgrade", "head").returncode == 0

    engine = sa.create_engine(migration_db_url)
    try:
        tables = set(sa.inspect(engine).get_table_names())
    finally:
        engine.dispose()

    missing = set(Model.metadata.tables) - tables
    assert not missing, f"Миграции не создали таблицы: {sorted(missing)}"


def test_no_pending_autogenerate_changes(migration_db_url: str) -> None:
    """Автогенерация после ``upgrade head`` не находит расхождений."""
    assert run_alembic(migration_db_url, "upgrade", "head").returncode == 0

    result = run_alembic(migration_db_url, "check")
    assert result.returncode == 0, result.stdout + result.stderr
