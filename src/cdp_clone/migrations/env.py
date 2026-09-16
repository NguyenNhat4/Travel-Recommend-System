import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from src.cdp_clone.app.infrastructure.tables import metadata

config = context.config
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name)

url = config.get_main_option("sqlalchemy.url") or os.environ.get(
    "CDP_DATABASE_URL", "postgresql+psycopg://cdp:cdp@localhost:5433/cdp"
)

if context.is_offline_mode():
    context.configure(url=url, target_metadata=metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=metadata)
        with context.begin_transaction():
            context.run_migrations()
