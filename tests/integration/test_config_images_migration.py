from alembic import command
from sqlalchemy import create_engine, inspect, text

from app.db.migrate import _build_alembic_config, check_migration_policy, check_schema_drift, run_upgrade


def test_empty_token_pool_preserves_historical_authentication_and_reversible_image_settings(tmp_path):
    url = "sqlite:///" + (tmp_path / "config-images.db").as_posix()
    previous = "20261022_000000_add_routing_priority_rules"
    run_upgrade(url, previous, bootstrap_legacy=False)
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text("""INSERT INTO api_keys(id,name,key_hash,key_prefix,is_active,created_at,
            account_assignment_scope_enabled,source_assignment_scope_enabled,apply_to_codex_model,
            traffic_class,usage_sections)
        VALUES ('historical','historical','unchanged-hash','sk-test',1,CURRENT_TIMESTAMP,
                0,0,0,'foreground','upstream_limits,account_pool_usage')""")
        )
    run_upgrade(url, "head", bootstrap_legacy=False)
    run_upgrade(url, "head", bootstrap_legacy=False)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM codex_config_api_tokens")) == 0
        assert connection.scalar(text("SELECT key_hash FROM api_keys")) == "unchanged-hash"
        assert "image_host_model" in {column["name"] for column in inspect(connection).get_columns("request_logs")}
    assert not check_migration_policy(url)
    assert not check_schema_drift(url)
    command.downgrade(_build_alembic_config(url), previous)
    with engine.connect() as connection:
        assert "codex_config_api_tokens" not in inspect(connection).get_table_names()
        assert "relay_image_routing_settings" not in inspect(connection).get_table_names()
        assert connection.scalar(text("SELECT key_hash FROM api_keys")) == "unchanged-hash"
    run_upgrade(url, "head", bootstrap_legacy=False)
    assert not check_schema_drift(url)
    engine.dispose()
