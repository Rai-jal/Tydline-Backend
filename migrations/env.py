import os
from logging.config import fileConfig
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

from alembic import context

# Load .env so DATABASE_URL is available when running alembic from the CLI
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Alembic config object
config = context.config

# Set up logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Pull DATABASE_URL from environment (overrides alembic.ini sqlalchemy.url)
# Convert asyncpg driver to psycopg2-compatible sync driver for Alembic
_db_url = os.environ["DATABASE_URL"]
_db_url = _db_url.replace("postgresql+asyncpg://", "postgresql://")
# ConfigParser uses % for interpolation — escape literal % chars in the URL
config.set_main_option("sqlalchemy.url", _db_url.replace("%", "%%"))

# Import all ORM models so Alembic can detect schema changes
from app.models.orm import (  # noqa: E402, F401
    AIGeneratedMessage,
    Notification,
    RiskAlert,
    Shipment,
    ShipmentEvent,
    User,
)
from app.db.session import Base  # noqa: E402

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
