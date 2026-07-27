import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context
from database import Base
import models


# Alembic Config object
config = context.config


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

# Get DATABASE_URL from environment
# Local: can come from your environment/.env setup
# Azure: comes from Container App environment variables
database_url = os.getenv("DATABASE_URL")

if database_url:
    # ConfigParser treats % as interpolation syntax.
    # Replace % with %% so encoded characters such as %40 work correctly.
    config.set_main_option(
        "sqlalchemy.url",
        database_url.replace("%", "%%")
    )


# ============================================================
# LOGGING CONFIGURATION
# ============================================================

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


# ============================================================
# SQLALCHEMY METADATA
# ============================================================

# Used by Alembic autogenerate
target_metadata = Base.metadata


# ============================================================
# OFFLINE MIGRATIONS
# ============================================================

def run_migrations_offline() -> None:
    """Run migrations in offline mode."""

    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# ============================================================
# ONLINE MIGRATIONS
# ============================================================

def run_migrations_online() -> None:
    """Run migrations in online mode."""

    connectable = engine_from_config(
        config.get_section(
            config.config_ini_section,
            {}
        ),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


# ============================================================
# RUN MIGRATIONS
# ============================================================

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()