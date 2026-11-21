from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.core.config import get_settings
from app.db.models import Base

config = context.config
if config.config_file_name and not config.attributes.get("skip_logging_config"):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Only these schemas belong to the app. The PostGIS image also creates tiger and
# topology schemas, and dbt owns staging and mart; autogenerate must ignore them.
OWNED_SCHEMAS = {"raw", "ops"}


def include_name(name: str | None, type_: str, parent_names: dict[str, str | None]) -> bool:
    if type_ == "schema":
        return name in OWNED_SCHEMAS
    return True


def _url() -> str:
    return config.attributes.get("url") or get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=Base.metadata,
        literal_binds=True,
        include_schemas=True,
        include_name=include_name,
        version_table_schema="ops",
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        # The version table lives in ops, so ops must exist before Alembic looks for it.
        connection.exec_driver_sql("CREATE SCHEMA IF NOT EXISTS ops")
        connection.commit()
        context.configure(
            connection=connection,
            target_metadata=Base.metadata,
            include_schemas=True,
            include_name=include_name,
            version_table_schema="ops",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
