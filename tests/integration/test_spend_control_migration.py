from alembic import command
from sqlalchemy import create_engine, inspect

from app.db.migrate import _build_alembic_config, check_migration_policy, check_schema_drift, run_upgrade


def test_spend_control_migration_is_additive_and_reversible(tmp_path):
    url = "sqlite:///" + (tmp_path / "budget.db").as_posix()
    previous = "20261027_010000_add_image_routing_settings"
    run_upgrade(url, previous, bootstrap_legacy=False)
    engine = create_engine(url)
    with engine.connect() as conn:
        assert "provider_billing_spend_controls" not in inspect(conn).get_table_names()
    run_upgrade(url, "head", bootstrap_legacy=False)
    run_upgrade(url, "head", bootstrap_legacy=False)
    assert not check_migration_policy(url)
    assert not check_schema_drift(url)
    command.downgrade(_build_alembic_config(url), previous)
    with engine.connect() as conn:
        assert "provider_billing_spend_controls" not in inspect(conn).get_table_names()
    run_upgrade(url, "head", bootstrap_legacy=False)
    assert not check_schema_drift(url)
    engine.dispose()
