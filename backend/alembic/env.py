from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context

import app.models  # noqa: F401  (registers every table on Base.metadata)
from app.core.config import get_settings
from app.db.base import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Models' metadata, used by `alembic revision --autogenerate`.
target_metadata = Base.metadata

# The URL comes from backend/.env (never from alembic.ini). It is passed
# straight to SQLAlchemy rather than through config.set_main_option(), which
# would choke on a "%" in a URL-encoded password.
DATABASE_URL = get_settings().database_url.get_secret_value()


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


def run_migrations_online() -> None:
    """Run migrations in 'online' mode against the live database."""
    connectable = create_engine(DATABASE_URL, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
