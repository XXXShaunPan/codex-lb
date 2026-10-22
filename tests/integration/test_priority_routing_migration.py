from alembic import command
from sqlalchemy import create_engine, inspect, text

from app.db.migrate import _build_alembic_config, check_migration_policy, check_schema_drift, run_upgrade


def test_priority_migration_preserves_weights_and_reversible_rules(tmp_path):
    url = "sqlite:///" + (tmp_path / "priorities.db").as_posix()
    previous = "20261020_000000_add_custom_routing_weights"
    run_upgrade(url, previous, bootstrap_legacy=False)
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text("""INSERT INTO accounts(id,email,plan_type,access_token_encrypted,
            refresh_token_encrypted,id_token_encrypted,last_refresh,status,codex_installation_id,routing_weight)
            VALUES ('a','a@example.test','plus',x'00',x'00',x'00',CURRENT_TIMESTAMP,'active','install',2.5)""")
        )
    run_upgrade(url, "head", bootstrap_legacy=False)
    with engine.begin() as connection:
        assert connection.scalar(text("SELECT routing_weight FROM accounts WHERE id='a'")) == 2.5
        connection.execute(
            text("""INSERT INTO relay_routing_rules(scope,target,normal_priority,low_priority,
            downgrade_percent,recovery_percent,quota_basis,allow_low_quota)
            VALUES ('plan','plus',10,30,20,25,'minimum',0)""")
        )
        connection.execute(
            text("""INSERT INTO relay_routing_quota_bands(account_id,low_quota,fingerprint,sample_at)
            VALUES ('a',1,'minimum:20:25',100)""")
        )
    run_upgrade(url, "head", bootstrap_legacy=False)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT low_quota FROM relay_routing_quota_bands")) == 1
        assert connection.scalar(text("SELECT allow_low_quota FROM relay_routing_rules")) == 0
    assert not check_migration_policy(url)
    assert not check_schema_drift(url)
    command.downgrade(_build_alembic_config(url), previous)
    with engine.connect() as connection:
        assert "relay_routing_rules" not in inspect(connection).get_table_names()
        assert connection.scalar(text("SELECT routing_weight FROM accounts WHERE id='a'")) == 2.5
    run_upgrade(url, "head", bootstrap_legacy=False)
    assert not check_schema_drift(url)
    engine.dispose()
