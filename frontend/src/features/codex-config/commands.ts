import awkEditor from "./edit_config.awk?raw";
import powershellEditor from "./edit_config.ps1?raw";

type Operation = "setup" | "cleanup";
function tomlString(value: string) {
  return JSON.stringify(value);
}
function settings(
  mode: Operation,
  apiKey: string,
  model: string,
  baseUrl: string,
) {
  const base = baseUrl.replace(/\/$/, "");
  return {
    mode,
    base_url: base,
    model_value: tomlString(model),
    token_value: tomlString(apiKey),
    base_value: tomlString(base),
    catalog_value: tomlString(base + "/models"),
  };
}
function encoded(value: unknown) {
  return btoa(
    Array.from(new TextEncoder().encode(JSON.stringify(value)), (byte) =>
      String.fromCharCode(byte),
    ).join(""),
  );
}
function awkString(value: string) {
  return (
    '"' +
    value
      .replace(/\\/g, "\\\\")
      .replace(/"/g, '\\"')
      .replace(/\n/g, "\\n")
      .replace(/\r/g, "\\r") +
    '"'
  );
}
function bashCommand(
  mode: Operation,
  apiKey: string,
  model: string,
  baseUrl: string,
) {
  const data = settings(mode, apiKey, model, baseUrl);
  const parameters = Object.entries({
    MODE: mode,
    BASE: data.base_url,
    V_MODEL: data.model_value,
    V_TOKEN: data.token_value,
    V_BASE: data.base_value,
    V_CATALOG: data.catalog_value,
  })
    .map(([key, value]) => key + "=" + awkString(value))
    .join("; ");
  return [
    "(",
    "set -eu",
    "umask 077",
    'codex_dir="${CODEX_HOME:-$HOME/.codex}"',
    'case "$codex_dir" in "~/"*) codex_dir="$HOME/${codex_dir#\\~/}";; esac',
    'config="$codex_dir/config.toml"',
    '[ ! -L "$config" ] || { echo "Refusing to replace a symlink; edit its target explicitly." >&2; exit 1; }',
    mode === "cleanup"
      ? '[ -f "$config" ] || { echo "No config.toml; nothing to remove."; exit 0; }'
      : 'mkdir -p "$codex_dir"',
    'temp_file="$(mktemp "$codex_dir/.codex-lb-config.XXXXXX")"',
    "trap 'rm -f \"$temp_file\"' EXIT HUP INT TERM",
    'source_file="$config"; [ -f "$source_file" ] || source_file=/dev/null',
    "status=0",
    'LC_ALL=C awk -f - "$source_file" > "$temp_file" <<\'CODEX_LB_NATIVE_AWK\' || status=$?',
    "BEGIN { " + parameters + " }",
    awkEditor.replace(/\r\n/g, "\n").trimEnd(),
    "CODEX_LB_NATIVE_AWK",
    '[ "$status" -ne 3 ] || { echo "No Codex-LB settings found; configuration unchanged."; exit 0; }',
    '[ "$status" -eq 0 ] || exit "$status"',
    'if [ -f "$config" ] && cmp -s "$config" "$temp_file"; then echo "Configuration already current."; exit 0; fi',
    'if [ -f "$config" ]; then',
    '  backup="$config.bak.$(date +%Y%m%d-%H%M%S).${temp_file##*.}"',
    '  cp -p "$config" "$backup"; chmod 600 "$backup"',
    '  printf "Backup: %s\\n" "$backup"',
    "fi",
    'chmod 600 "$temp_file"; mv -f "$temp_file" "$config"',
    'echo "' +
      (mode === "setup"
        ? "Codex-LB configured"
        : "Codex-LB settings removed; other settings retained") +
      '. Restart Codex."',
    ")",
  ].join("\n");
}
function windowsCommand(
  mode: Operation,
  apiKey: string,
  model: string,
  baseUrl: string,
) {
  return [
    "& {",
    "$ErrorActionPreference = 'Stop'",
    "$RelaySettings = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('" +
      encoded(settings(mode, apiKey, model, baseUrl)) +
      "')) | ConvertFrom-Json",
    "$codexDir = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path ([Environment]::GetFolderPath('UserProfile')) '.codex' }",
    "if ($codexDir.StartsWith('~/') -or $codexDir.StartsWith('~\\')) { $codexDir = Join-Path ([Environment]::GetFolderPath('UserProfile')) $codexDir.Substring(2) }",
    "$config = [IO.Path]::GetFullPath((Join-Path $codexDir 'config.toml'))",
    "$exists = [IO.File]::Exists($config)",
    "if ($exists -and (([IO.File]::GetAttributes($config) -band [IO.FileAttributes]::ReparsePoint) -ne 0)) { throw 'Refusing to replace a symlink; edit its target explicitly.' }",
    ...(mode === "cleanup"
      ? [
          "if (-not $exists) { Write-Host 'No config.toml; nothing to remove.'; return }",
        ]
      : []),
    "$Original = if ($exists) { [IO.File]::ReadAllText($config) } else { '' }",
    powershellEditor.replace(/\r\n/g, "\n").trimEnd(),
    "if ($Updated -ceq $Original) { Write-Host 'Configuration already current.'; return }",
    "[void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($config))",
    "$suffix = (Get-Date -Format 'yyyyMMdd-HHmmss') + '.' + [Guid]::NewGuid().ToString('N')",
    "$temporary = Join-Path ([IO.Path]::GetDirectoryName($config)) ('.codex-lb-config.' + $suffix)",
    "try {",
    "  [IO.File]::WriteAllText($temporary, $Updated, [Text.UTF8Encoding]::new($false))",
    "  if ($exists) {",
    "    $backup = $config + '.bak.' + $suffix",
    "    [IO.File]::Replace($temporary, $config, $backup)",
    "    Write-Host ('Backup: ' + $backup)",
    "  } else { [IO.File]::Move($temporary, $config) }",
    "} finally { if ([IO.File]::Exists($temporary)) { [IO.File]::Delete($temporary) } }",
    "Write-Host '" +
      (mode === "setup"
        ? "Codex-LB configured"
        : "Codex-LB settings removed; other settings retained") +
      ". Restart Codex.'",
    "}",
  ].join("\r\n");
}
export function buildBashCodexCommand(
  apiKey: string,
  model: string,
  baseUrl: string,
) {
  return bashCommand("setup", apiKey, model, baseUrl);
}
export function buildWindowsCodexCommand(
  apiKey: string,
  model: string,
  baseUrl: string,
) {
  return windowsCommand("setup", apiKey, model, baseUrl);
}
function websiteBase() {
  return location.origin.replace(/\/$/, "") + "/backend-api/codex";
}
export function buildCodexCommands(apiKey: string, model: string) {
  const base = websiteBase();
  return {
    macos: buildBashCodexCommand(apiKey, model, base),
    linux: buildBashCodexCommand(apiKey, model, base),
    windows: buildWindowsCodexCommand(apiKey, model, base),
  };
}
export function buildBashRestoreCommand(baseUrl: string = websiteBase()) {
  return bashCommand("cleanup", "", "", baseUrl);
}
export function buildWindowsRestoreCommand(baseUrl: string = websiteBase()) {
  return windowsCommand("cleanup", "", "", baseUrl);
}
export function buildCodexRestoreCommands() {
  return {
    macos: buildBashRestoreCommand(),
    linux: buildBashRestoreCommand(),
    windows: buildWindowsRestoreCommand(),
  };
}
