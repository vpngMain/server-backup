import sys
from pathlib import Path
from logging.config import fileConfig

# Kořen projektu na path pro import app
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, pool
from alembic import context

from app.config import DATABASE_URL
from app.db import Base
from app.models import *  # noqa: F401, F403 - načíst všechny modely

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Nastavit URL z aplikace (podporovat SQLite path)
config.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
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
    """Run migrations in 'online' mode."""
    connectable = context.config.attributes.get("connection", None)
    if connectable is None:
        connectable = create_engine(
            config.get_main_option("sqlalchemy.url"),
            poolclass=pool.NullPool,
        )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
