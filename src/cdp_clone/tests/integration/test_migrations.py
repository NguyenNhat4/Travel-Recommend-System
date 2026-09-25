from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from src.cdp_clone.app.infrastructure.tables import metadata

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def test_migration_matches_table_definitions(tmp_path):
    url = f"sqlite:///{tmp_path / 'cdp.db'}"
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("sqlalchemy.url", url)
    config.attributes["configure_logger"] = False
    command.upgrade(config, "head")

    inspector = inspect(create_engine(url))
    for table in metadata.sorted_tables:
        migrated = {c["name"]: c["nullable"] for c in inspector.get_columns(table.name)}
        declared = {c.name: c.nullable for c in table.columns}
        assert migrated == declared, table.name
    unique = inspector.get_unique_constraints("events")
    assert [u["column_names"] for u in unique] == [["cdp_user_id", "event_id"]]
