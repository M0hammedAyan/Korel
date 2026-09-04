import os
from logging.config import fileConfig
from urllib.parse import quote_plus

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Autogenerate metadata is declared in backend.schema_metadata.
try:
    from backend.schema_metadata import metadata as target_metadata
except Exception:
    target_metadata = None


def get_url():
    # Prefer direct DATABASE_URL env var; otherwise, try alembic.ini substitution
    direct_url = os.environ.get('DATABASE_URL') or os.environ.get('SQLALCHEMY_DATABASE_URL')
    if direct_url:
        return direct_url

    if os.environ.get("DB_TYPE", "sqlite").lower() == "postgres":
        user = quote_plus(os.environ.get("DB_USER", "postgres"))
        password = quote_plus(os.environ.get("DB_PASS", ""))
        host = os.environ.get("DB_HOST", "localhost")
        port = os.environ.get("DB_PORT", "5432")
        database = os.environ.get("DB_NAME", "koral")
        return f"postgresql://{user}:{password}@{host}:{port}/{database}"

    return config.get_main_option('sqlalchemy.url')


def run_migrations_offline():
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    configuration = config.get_section(config.config_ini_section)
    configuration['sqlalchemy.url'] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix='sqlalchemy.',
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
