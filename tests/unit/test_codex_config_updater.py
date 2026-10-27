import runpy
import tomllib
from pathlib import Path

import pytest

UPDATER = Path(__file__).parents[2] / "frontend/src/features/codex-config/update_config.py"
SETTINGS = {"token": "sk-test-'\"$中文", "model": "gpt-6-astra", "base_url": "https://relay.test/backend-api/codex"}


@pytest.mark.parametrize(
    "original,provider",
    [
        ("", "openai_https"),
        ('model_provider="openai"\n[features]\nshell_tool=true\n', "openai_https"),
        ('model_provider="mine"\n[model_providers.mine]\nname="old"\nenv_key="OLD"\n', "mine"),
        ('model_provider="missing"\n[model_providers.single]\nname="old"', "single"),
        ('model_providers.openai_https.name="old"\nfeatures.shell_tool=true\n', "openai_https"),
        ('model_provider="name.with.dot"\n[model_providers."name.with.dot"]\nname="old"', "name.with.dot"),
        ('[model_providers.other]\nname="Other"\n[model_providers.openai_https]\nname="Existing"', "openai_https"),
    ],
)
def test_config_update_preserves_unrelated_content_and_is_idempotent(tmp_path, monkeypatch, original, provider):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    unrelated = (
        '\n# Keep projects verbatim\n[projects."C:/my project"]\ntrust_level="trusted"\n'
        'note="""[features]\nnot a table"""\n[[example]]\nx=1\n[[example]]\nx=2\n'
    )
    original += unrelated
    path = tmp_path / "config.toml"
    path.write_text(original, encoding="utf-8")
    update = runpy.run_path(str(UPDATER))["update_config"]
    update(SETTINGS)
    text = path.read_text(encoding="utf-8")
    parsed = tomllib.loads(text)
    assert parsed["model_provider"] == provider
    selected = parsed["model_providers"][provider]
    assert selected["name"] == "OpenAI"
    assert selected["experimental_bearer_token"] == SETTINGS["token"]
    assert selected["requires_openai_auth"] is True
    assert selected["http_headers"]["x-openai-actor-authorization"] == "codex-lb"
    assert selected["model_catalog_url"] == SETTINGS["base_url"] + "/models"
    assert "env_key" not in selected
    assert parsed["features"]["api_key_model_discovery"] is True
    assert unrelated.strip() in text
    backups = list(tmp_path.glob("config.toml.bak.*"))
    assert len(backups) == 1 and backups[0].read_text(encoding="utf-8") == original
    update(SETTINGS)
    assert path.read_text(encoding="utf-8") == text
    assert len(list(tmp_path.glob("config.toml.bak.*"))) == 1
    assert not (tmp_path / "codex-lb.key").exists()


def test_invalid_config_is_never_overwritten(tmp_path, monkeypatch):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    path = tmp_path / "config.toml"
    path.write_text("[features\n", encoding="utf-8")
    with pytest.raises(tomllib.TOMLDecodeError):
        runpy.run_path(str(UPDATER))["update_config"](SETTINGS)
    assert path.read_text(encoding="utf-8") == "[features\n"
    assert not list(tmp_path.glob("*.bak.*"))


def test_config_headers_and_other_provider_preserved(tmp_path, monkeypatch):
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    path = tmp_path / "config.toml"
    path.write_text(
        """model_provider = "mine"
[model_providers.other]
name="untouched"
[model_providers.mine]
auth={command="old"}
http_headers={Authorization="old", X-OpenAI-Actor-Authorization="old", X-Custom="keep"}
env_http_headers={Authorization="OLD", X-Custom="KEEP"}
""",
        encoding="utf-8",
    )
    runpy.run_path(str(UPDATER))["update_config"](SETTINGS)
    providers = tomllib.loads(path.read_text(encoding="utf-8"))["model_providers"]
    assert providers["other"] == {"name": "untouched"}
    assert "auth" not in providers["mine"]
    assert providers["mine"]["http_headers"] == {"X-Custom": "keep", "x-openai-actor-authorization": "codex-lb"}
    assert providers["mine"]["env_http_headers"] == {"X-Custom": "KEEP"}
