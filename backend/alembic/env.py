from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context

import app.models  # noqa: F401  (registers every table on Base.metadata)
from app.core.config import get_settings
from app.db.base import Base


config = context.config


if config.config_file_name is not None:
    fileConfig(config.config_file_name)


target_metadata = Base.metadata


# DIRECT_DATABASE_URL when it is set (e.g. Neon's direct, non-pooled URL), otherwise
# DATABASE_URL. The FastAPI app always uses DATABASE_URL (app/db/session.py).
DATABASE_URL = get_settings().migration_database_url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL to stdout with `--sql`)."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def _migrate(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode against the live database."""
    # The test suite passes its own connection (to namat_test); the normal
    # `alembic` command doesn't, and uses the URL chosen above.
    provided = config.attributes.get("connection")
    if provided is not None:
        _migrate(provided)
        return

    connectable = create_engine(DATABASE_URL, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        _migrate(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
