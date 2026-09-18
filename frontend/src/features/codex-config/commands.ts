export function tomlString(value: string) {
  return `"${String(value).replace(/\\/g, "\\\\").replace(/"/g, '\\"').replace(/\r/g, "\\r").replace(/\n/g, "\\n")}"`;
}

export function shellQuote(value: string) {
  return `'${String(value).replace(/'/g, `'"'"'`)}'`;
}

export function powershellQuote(value: string) {
  return `'${String(value).replace(/'/g, "''")}'`;
}

export function buildBashCodexCommand(apiKey: string, model: string, baseUrl: string) {
  const provider = [
    "[model_providers.codex_lb]",
    'name = "Codex LB"',
    `base_url = ${tomlString(baseUrl)}`,
    'wire_api = "responses"',
    "supports_websockets = false",
    "",
    "[model_providers.codex_lb.auth]",
    'command = "sh"',
    'args = ["-c", "cat \\"${CODEX_HOME:-$HOME/.codex}/codex-lb.key\\""]',
  ].join("\n");
  return [
    "set -euo pipefail",
    'CODEX_DIR="${CODEX_HOME:-$HOME/.codex}"',
    'CONFIG="$CODEX_DIR/config.toml"',
    'KEY_FILE="$CODEX_DIR/codex-lb.key"',
    'STAMP="$(date +%Y%m%d-%H%M%S)"',
    'mkdir -p "$CODEX_DIR"',
    '[ ! -f "$CONFIG" ] || cp -p "$CONFIG" "$CONFIG.bak.$STAMP"',
    '[ ! -f "$KEY_FILE" ] || cp -p "$KEY_FILE" "$KEY_FILE.bak.$STAMP"',
    `printf '%s' ${shellQuote(apiKey)} > "$KEY_FILE"`,
    'chmod 600 "$KEY_FILE"',
    'TMP="$(mktemp "$CODEX_DIR/config.toml.tmp.XXXXXX")"',
    "trap 'rm -f \"$TMP\"' EXIT",
    'if [ -f "$CONFIG" ]; then',
    `  awk '
BEGIN { in_provider=0; seen_table=0 }
/^[[:space:]]*\\[model_providers\\.codex_lb(\\.auth)?\\][[:space:]]*$/ { in_provider=1; next }
in_provider && /^[[:space:]]*\\[/ { in_provider=0 }
in_provider { next }
!seen_table && /^[[:space:]]*\\[/ { seen_table=1 }
!seen_table && /^[[:space:]]*(model|model_provider)[[:space:]]*=/ { next }
{ print }
' "$CONFIG" > "$TMP"`,
    "else",
    '  : > "$TMP"',
    "fi",
    "{",
    `  printf '%s\\n' ${shellQuote(`model = ${tomlString(model)}`)} 'model_provider = "codex_lb"' ''`,
    '  cat "$TMP"',
    "  printf '\\n'",
    "  cat <<'CODEX_LB_CONFIG'",
    provider,
    "CODEX_LB_CONFIG",
    '} > "$CONFIG"',
    'chmod 600 "$CONFIG"',
    'rm -f "$TMP"',
    "trap - EXIT",
    'printf \'Codex LB configured. Backup: %s.bak.%s\\n\' "$CONFIG" "$STAMP"',
  ].join("\n");
}

export function buildWindowsCodexCommand(apiKey: string, model: string, baseUrl: string) {
  const header = `model = ${tomlString(model)}\nmodel_provider = "codex_lb"`;
  const provider = [
    "",
    "[model_providers.codex_lb]",
    'name = "Codex LB"',
    `base_url = ${tomlString(baseUrl)}`,
    'wire_api = "responses"',
    "supports_websockets = false",
    "",
    "[model_providers.codex_lb.auth]",
    'command = "powershell.exe"',
    'args = ["-NoProfile", "-Command", "$d=if($env:CODEX_HOME){$env:CODEX_HOME}else{Join-Path $env:USERPROFILE \'.codex\'};[Console]::Out.Write((Get-Content -Raw (Join-Path $d \'codex-lb.key\')).Trim())"]',
    "",
  ].join("\n");
  return [
    "$ErrorActionPreference = 'Stop'",
    "$codexDir = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }",
    "$config = Join-Path $codexDir 'config.toml'",
    "$keyFile = Join-Path $codexDir 'codex-lb.key'",
    "$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'",
    "New-Item -ItemType Directory -Path $codexDir -Force | Out-Null",
    "if (Test-Path -LiteralPath $config) { Copy-Item -LiteralPath $config -Destination \"$config.bak.$stamp\" }",
    "if (Test-Path -LiteralPath $keyFile) { Copy-Item -LiteralPath $keyFile -Destination \"$keyFile.bak.$stamp\" }",
    "$utf8 = [Text.UTF8Encoding]::new($false)",
    `[IO.File]::WriteAllText($keyFile, ${powershellQuote(apiKey)}, $utf8)`,
    "$identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name",
    "& icacls $keyFile /inheritance:r /grant:r \"${identity}:(R,W)\" | Out-Null",
    "$lines = if (Test-Path -LiteralPath $config) { [IO.File]::ReadAllLines($config) } else { @() }",
    "$filtered = [Collections.Generic.List[string]]::new()",
    "$inProvider = $false; $seenTable = $false",
    "foreach ($line in $lines) {",
    "  if ($line -match '^\\s*\\[model_providers\\.codex_lb(?:\\.auth)?\\]\\s*$') { $inProvider = $true; continue }",
    "  if ($inProvider -and $line -match '^\\s*\\[') { $inProvider = $false }",
    "  if ($inProvider) { continue }",
    "  if (-not $seenTable -and $line -match '^\\s*\\[') { $seenTable = $true }",
    "  if (-not $seenTable -and $line -match '^\\s*(model|model_provider)\\s*=') { continue }",
    "  [void]$filtered.Add($line)",
    "}",
    `$header = @'\n${header}\n'@`,
    `$provider = @'\n${provider}'@`,
    "$content = $header + [Environment]::NewLine + (($filtered -join [Environment]::NewLine).Trim()) + $provider",
    "[IO.File]::WriteAllText($config, $content, $utf8)",
    "Write-Host \"Codex LB configured. Backup: $config.bak.$stamp\"",
  ].join("\r\n");
}

export function buildCodexCommands(apiKey: string, model: string) {
  const baseUrl = `${location.origin.replace(/\/$/, "")}/backend-api/codex`;
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
    'KEY_FILE="$CODEX_DIR/codex-lb.key"',
    'LATEST_CONFIG="$(ls -1t "$CONFIG".bak.* 2>/dev/null | head -n 1 || true)"',
    'if [ -z "$LATEST_CONFIG" ]; then echo "No Codex config backup found: $CONFIG.bak.*" >&2; exit 1; fi',
    'STAMP="$(date +%Y%m%d-%H%M%S)"',
    '[ ! -f "$CONFIG" ] || cp -p "$CONFIG" "$CONFIG.before-restore.$STAMP"',
    'BACKUP_SUFFIX="${LATEST_CONFIG##*.bak.}"',
    'cp -p "$LATEST_CONFIG" "$CONFIG"',
    'MATCHING_KEY="$KEY_FILE.bak.$BACKUP_SUFFIX"',
    'if [ -f "$MATCHING_KEY" ]; then',
    '  [ ! -f "$KEY_FILE" ] || cp -p "$KEY_FILE" "$KEY_FILE.before-restore.$STAMP"',
    '  cp -p "$MATCHING_KEY" "$KEY_FILE"',
    '  chmod 600 "$KEY_FILE"',
    'else',
    '  echo "No matching key backup found; the current key file was left unchanged."',
    'fi',
    'chmod 600 "$CONFIG"',
    'printf \'Restored Codex config from %s. Restart Codex to apply it.\\n\' "$LATEST_CONFIG"',
  ].join("\n");
}

export function buildWindowsRestoreCommand() {
  return [
    "$ErrorActionPreference = 'Stop'",
    "$codexDir = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }",
    "$config = Join-Path $codexDir 'config.toml'",
    "$keyFile = Join-Path $codexDir 'codex-lb.key'",
    "$backup = Get-ChildItem -Path \"$config.bak.*\" -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1",
    "if (-not $backup) { throw \"No Codex config backup found: $config.bak.*\" }",
    "$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'",
    "if (Test-Path -LiteralPath $config) { Copy-Item -LiteralPath $config -Destination \"$config.before-restore.$stamp\" }",
    "$prefix = \"$config.bak.\"",
    "$backupSuffix = $backup.FullName.Substring($prefix.Length)",
    "Copy-Item -LiteralPath $backup.FullName -Destination $config -Force",
    "$keyBackup = \"$keyFile.bak.$backupSuffix\"",
    "if (Test-Path -LiteralPath $keyBackup) {",
    "  if (Test-Path -LiteralPath $keyFile) { Copy-Item -LiteralPath $keyFile -Destination \"$keyFile.before-restore.$stamp\" }",
    "  Copy-Item -LiteralPath $keyBackup -Destination $keyFile -Force",
    "  $identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name",
    "  & icacls $keyFile /inheritance:r /grant:r \"${identity}:(R,W)\" | Out-Null",
    "} else {",
    "  Write-Warning 'No matching key backup found; the current key file was left unchanged.'",
    "}",
    "Write-Host \"Restored Codex config from $($backup.FullName). Restart Codex to apply it.\"",
  ].join("\r\n");
}

export function buildCodexRestoreCommands() {
  return {
    macos: buildBashRestoreCommand(),
    linux: buildBashRestoreCommand(),
    windows: buildWindowsRestoreCommand(),
  };
}
