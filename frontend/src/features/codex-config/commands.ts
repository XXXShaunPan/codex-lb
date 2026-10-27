import updaterSource from "./update_config.py?raw";

function updateScript(apiKey: string, model: string, baseUrl: string): string {
  const payload = JSON.stringify({ token: apiKey, model, base_url: baseUrl });
  const encoded = btoa(
    Array.from(new TextEncoder().encode(payload), (byte) =>
      String.fromCharCode(byte),
    ).join(""),
  );
  return (
    updaterSource +
    "\nupdate_config(json.loads(base64.b64decode('" +
    encoded +
    "').decode('utf-8')))\n"
  );
}

export function buildBashCodexCommand(
  apiKey: string,
  model: string,
  baseUrl: string,
) {
  return [
    "set -euo pipefail",
    "command -v python3 >/dev/null || { echo 'Python 3.11+ is required; config.toml was not changed.' >&2; exit 1; }",
    "python3 - <<'CODEX_LB_CONFIG_PY'",
    updateScript(apiKey, model, baseUrl),
    "CODEX_LB_CONFIG_PY",
  ].join("\n");
}

export function buildWindowsCodexCommand(
  apiKey: string,
  model: string,
  baseUrl: string,
) {
  return [
    "$ErrorActionPreference = 'Stop'",
    "$runner = Get-Command py -ErrorAction SilentlyContinue",
    "$pythonArgs = @('-3', '-')",
    "if (-not $runner) { $runner = Get-Command python -ErrorAction SilentlyContinue; $pythonArgs = @('-') }",
    "if (-not $runner) { throw 'Python 3.11+ is required; config.toml was not changed.' }",
    "$script = @'",
    updateScript(apiKey, model, baseUrl),
    "'@",
    "$script | & $runner.Source @pythonArgs",
    "if ($LASTEXITCODE -ne 0) { throw 'Configuration update failed; inspect the error above.' }",
  ].join("\r\n");
}

export function buildCodexCommands(apiKey: string, model: string) {
  const baseUrl = location.origin.replace(/\/$/, "") + "/backend-api/codex";
  return {
    macos: buildBashCodexCommand(apiKey, model, baseUrl),
    linux: buildBashCodexCommand(apiKey, model, baseUrl),
    windows: buildWindowsCodexCommand(apiKey, model, baseUrl),
  };
}

export function buildBashRestoreCommand() {
  return [
    "set -euo pipefail",
    'CODEX_DIR="${CODEX_HOME:-$HOME/.codex}"',
    'CONFIG="$CODEX_DIR/config.toml"',
    'LATEST_CONFIG="$(ls -1t "$CONFIG".bak.* 2>/dev/null | head -n 1 || true)"',
    'if [ -z "$LATEST_CONFIG" ]; then echo "No Codex config backup found: $CONFIG.bak.*" >&2; exit 1; fi',
    'STAMP="$(date +%Y%m%d-%H%M%S)"',
    '[ ! -f "$CONFIG" ] || cp -p "$CONFIG" "$CONFIG.before-restore.$STAMP"',
    'cp -p "$LATEST_CONFIG" "$CONFIG"',
    'chmod 600 "$CONFIG"',
    "printf 'Restored Codex config from %s. Restart Codex to apply it.\\n' \"$LATEST_CONFIG\"",
  ].join("\n");
}

export function buildWindowsRestoreCommand() {
  return [
    "$ErrorActionPreference = 'Stop'",
    "$codexDir = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }",
    "$config = Join-Path $codexDir 'config.toml'",
    '$backup = Get-ChildItem -Path "$config.bak.*" -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1',
    'if (-not $backup) { throw "No Codex config backup found: $config.bak.*" }',
    "$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'",
    'if (Test-Path -LiteralPath $config) { Copy-Item -LiteralPath $config -Destination "$config.before-restore.$stamp" }',
    "Copy-Item -LiteralPath $backup.FullName -Destination $config -Force",
    'Write-Host "Restored Codex config from $($backup.FullName). Restart Codex to apply it."',
  ].join("\r\n");
}

export function buildCodexRestoreCommands() {
  return {
    macos: buildBashRestoreCommand(),
    linux: buildBashRestoreCommand(),
    windows: buildWindowsRestoreCommand(),
  };
}
