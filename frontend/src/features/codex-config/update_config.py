"""Self-contained updater embedded in the generated Bash/PowerShell command."""
import sys

if sys.version_info < (3, 11):
    raise SystemExit("Python 3.11 or newer is required; config.toml was not changed.")

import base64
import datetime
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import tomllib


def _key(value):
    return value if re.fullmatch(r"[A-Za-z0-9_-]+", value) else json.dumps(value, ensure_ascii=False)


def _value(value):
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (int, float)):
        return str(value).lower()
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    if isinstance(value, list):
        return "[" + ", ".join(_value(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{ " + ", ".join(_key(key) + " = " + _value(item) for key, item in value.items()) + " }"
    raise ValueError("Unsupported TOML value; config.toml was not changed")


def _path(text, table=False):
    probe = "__relay_probe__"
    parsed = tomllib.loads(text + "\n" + probe + " = true" if table else text + " = true")
    result = []
    while isinstance(parsed, (dict, list)):
        if isinstance(parsed, list):
            parsed = parsed[-1]
        if probe in parsed:
            return result
        name = next(iter(parsed))
        result.append(name)
        parsed = parsed[name]
    return result


def _scan(line, state):
    quote, depth = state
    index = 0
    while index < len(line):
        char = line[index]
        if quote:
            if quote.startswith('"') and char == "\\":
                index += 2
                continue
            if line.startswith(quote, index):
                index += len(quote)
                quote = None
                continue
        else:
            if char == "#":
                break
            if char in "\"'":
                quote = char * 3 if line.startswith(char * 3, index) else char
                index += len(quote)
                continue
            if char in "[{":
                depth += 1
            elif char in "]}":
                depth -= 1
        index += 1
    return quote, depth


def _retained_text(original):
    """Retain every unrelated section, including comments and multiline strings."""
    lines = original.splitlines(keepends=True)
    output = []
    state = (None, 0)
    section = []
    drop_statement = False
    for line in lines:
        stripped = line.lstrip()
        top = state == (None, 0)
        if top and stripped.startswith("#"):
            output.append(line)
            continue
        if top and stripped.startswith("["):
            section = _path(stripped, table=True)
            drop_statement = False
            if not section or section[0] not in {"features", "model_providers"}:
                output.append(line)
            continue
        if top and not section and stripped and not stripped.startswith("#") and "=" in stripped:
            # Quoted keys may contain '='; try each boundary until a valid key
            # path parses, without ever interpreting the value as a key.
            parsed_path = None
            for match in re.finditer("=", line):
                try:
                    parsed_path = _path(line[:match.start()])
                    break
                except tomllib.TOMLDecodeError:
                    continue
            drop_statement = bool(parsed_path and parsed_path[0] in {"model", "model_provider", "features", "model_providers"})
        state = _scan(line, state)
        if not (section and section[0] in {"features", "model_providers"}) and not drop_statement:
            output.append(line)
        if state == (None, 0):
            drop_statement = False
    return "".join(output)


def update_config(settings):
    directory = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser()
    path = directory / "config.toml"
    raw = path.read_bytes() if path.exists() else b""
    original = raw.decode("utf-8-sig")
    parsed = tomllib.loads(original)
    providers = parsed.get("model_providers", {})
    if not isinstance(providers, dict) or not all(isinstance(value, dict) for value in providers.values()):
        raise ValueError("model_providers must contain provider tables; config.toml was not changed")
    active = parsed.get("model_provider")
    reserved = {"openai", "ollama", "lmstudio"}
    custom = [name for name in providers if name not in reserved]
    if isinstance(active, str) and active in custom:
        provider_id = active
    elif "openai_https" in providers:
        provider_id = "openai_https"
    elif len(custom) == 1:
        provider_id = custom[0]
    else:
        provider_id = "openai_https"
    provider = dict(providers.get(provider_id, {}))
    for obsolete in ("auth", "env_key", "env_key_instructions"):
        provider.pop(obsolete, None)
    headers = {key: value for key, value in provider.get("http_headers", {}).items()
               if key.lower() not in {"authorization", "x-openai-actor-authorization"}}
    headers["x-openai-actor-authorization"] = "codex-lb"
    if isinstance(provider.get("env_http_headers"), dict):
        provider["env_http_headers"] = {key: value for key, value in provider["env_http_headers"].items()
                                        if key.lower() not in {"authorization", "x-openai-actor-authorization"}}
    base_url = settings["base_url"].rstrip("/")
    provider.update(name="OpenAI", base_url=base_url, model_catalog_url=base_url + "/models",
                    wire_api="responses", experimental_bearer_token=settings["token"],
                    requires_openai_auth=True, http_headers=headers, supports_websockets=False)
    providers[provider_id] = provider
    features = dict(parsed.get("features", {}))
    features["api_key_model_discovery"] = True
    parts = ["model = " + _value(settings["model"]), "model_provider = " + _value(provider_id), "",
             _retained_text(original).strip("\r\n"), "", "[features]"]
    parts.extend(_key(key) + " = " + _value(value) for key, value in features.items())
    for name, values in providers.items():
        parts.extend(["", "[model_providers." + _key(name) + "]"])
        parts.extend(_key(key) + " = " + _value(value) for key, value in values.items())
    result = "\n".join(parts).rstrip() + "\n"
    # Validate the final syntax and semantics before touching the original.
    expected = dict(parsed)
    expected.update(model=settings["model"], model_provider=provider_id, features=features, model_providers=providers)
    if tomllib.loads(result) != expected:
        raise ValueError("Configuration validation failed; config.toml was not changed")
    if result == original:
        print("Codex configuration is already current.")
        return
    directory.mkdir(parents=True, exist_ok=True)
    if path.exists():
        backup = path.with_name(path.name + ".bak." + datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
        shutil.copy2(path, backup)
        if os.name != "nt":
            backup.chmod(0o600)
        print("Backup:", backup)
    descriptor, temporary = tempfile.mkstemp(prefix="config.toml.tmp.", dir=directory)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(result)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    if os.name != "nt":
        path.chmod(0o600)
    print("Configured provider:", provider_id, "- fully restart Codex to apply.")
