from alembic import command
from sqlalchemy import create_engine, inspect, text

from app.db.migrate import _build_alembic_config, check_migration_policy, check_schema_drift, run_upgrade


def test_existing_accounts_receive_default_and_migration_is_reversible(tmp_path):
    url = "sqlite:///" + (tmp_path / "weights.db").as_posix()
    previous = "20260918_010000_add_visitor_accounts"
    run_upgrade(url, previous, bootstrap_legacy=False)
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text("""
            INSERT INTO accounts(id,email,plan_type,access_token_encrypted,refresh_token_encrypted,
                id_token_encrypted,last_refresh,status,codex_installation_id)
            VALUES ('migration-a','a@example.test','plus',x'00',x'00',x'00',
                CURRENT_TIMESTAMP,'active','installation-test')
        """)
        )
        connection.execute(
            text(
                "INSERT INTO model_sources(id,name,base_url) VALUES ('migration-source','source','https://example.invalid/v1')"
            )
        )
    run_upgrade(url, "head", bootstrap_legacy=False)
    with engine.begin() as connection:
        assert connection.scalar(text("SELECT routing_weight FROM accounts WHERE id='migration-a'")) == 1
        assert connection.scalar(text("SELECT routing_weight FROM model_sources WHERE id='migration-source'")) == 1
        connection.execute(text("UPDATE accounts SET routing_weight=2.5 WHERE id='migration-a'"))
    run_upgrade(url, "head", bootstrap_legacy=False)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT routing_weight FROM accounts WHERE id='migration-a'")) == 2.5
    assert not check_migration_policy(url)
    assert not check_schema_drift(url)
    command.downgrade(_build_alembic_config(url), previous)
    with engine.connect() as connection:
        assert "routing_weight" not in {column["name"] for column in inspect(connection).get_columns("accounts")}
        assert connection.scalar(text("SELECT COUNT(*) FROM accounts")) == 1
    run_upgrade(url, "head", bootstrap_legacy=False)
    assert not check_schema_drift(url)
    engine.dispose()
