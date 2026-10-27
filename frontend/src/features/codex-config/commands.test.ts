/// <reference types="node" />
import {
  mkdtempSync,
  readFileSync,
  readdirSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { delimiter, join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { describe, expect, it } from "vitest";
import {
  buildBashCodexCommand,
  buildWindowsCodexCommand,
  buildCodexCommands,
  buildCodexRestoreCommands,
} from "./commands";

const token = "sk-test-'\"$not_a_shell_command-中文";
const baseUrl = "https://relay.example.test:8443/backend-api/codex";

describe("relay Codex configuration", () => {
  it("uses the website origin and carries credentials as encoded data, not shell syntax", () => {
    const commands = buildCodexCommands(token, "gpt-6-astra");
    expect(commands.linux).not.toContain(token);
    expect(commands.windows).toContain("$LASTEXITCODE");
    expect(commands.macos).toBe(commands.linux);
    const payload = JSON.parse(
      Buffer.from(
        commands.linux.match(/base64.b64decode\('([^']+)'\)/)![1],
        "base64",
      ).toString(),
    );
    expect(payload).toEqual({
      token,
      model: "gpt-6-astra",
      base_url: location.origin + "/backend-api/codex",
    });
    expect(commands.linux).not.toContain("codex-lb.key");
    expect(buildCodexRestoreCommands().windows).toContain("before-restore");
    expect(buildCodexRestoreCommands().linux).toContain("before-restore");
  });

  it("executes the native shell command, preserves unrelated settings and backs up exactly once", () => {
    const dir = mkdtempSync(join(tmpdir(), "relay config 测试-"));
    const original =
      '# keep this comment\nmodel_provider = "existing"\n[features]\nshell_tool = true\n[model_providers.existing]\nname="Previous"\nenv_key="OLD_KEY"\n[projects."/my/project"]\ntrust_level="trusted"\n';
    writeFileSync(join(dir, "config.toml"), original);
    const windows = process.platform === "win32";
    const command = windows
      ? buildWindowsCodexCommand(token, "gpt-6-astra", baseUrl)
      : buildBashCodexCommand(token, "gpt-6-astra", baseUrl);
    const script = join(dir, windows ? "run.ps1" : "run.sh");
    writeFileSync(script, command);
    const env = {
      ...process.env,
      CODEX_HOME: dir,
      PATH:
        resolve("../.venv", windows ? "Scripts" : "bin") +
        delimiter +
        process.env.PATH,
    };
    const run = () =>
      spawnSync(
        windows ? "powershell.exe" : "bash",
        windows
          ? ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script]
          : [script],
        { env, encoding: "utf8", timeout: 20000 },
      );
    try {
      const first = run();
      expect(first.status, first.stderr).toBe(0);
      const result = readFileSync(join(dir, "config.toml"), "utf8");
      expect(result).toContain("[model_providers.existing]");
      expect(result).toContain('name = "OpenAI"');
      expect(result).toContain("api_key_model_discovery = true");
      expect(result).toContain("shell_tool = true");
      expect(result).toContain('[projects."/my/project"]');
      expect(result).toContain(baseUrl + "/models");
      expect(result).not.toContain("env_key");
      const backups = readdirSync(dir).filter((file) =>
        file.startsWith("config.toml.bak."),
      );
      expect(backups).toHaveLength(1);
      expect(readFileSync(join(dir, backups[0]), "utf8")).toBe(original);
      expect(run().status).toBe(0);
      expect(readFileSync(join(dir, "config.toml"), "utf8")).toBe(result);
      expect(
        readdirSync(dir).filter((file) => file.startsWith("config.toml.bak.")),
      ).toHaveLength(1);
      expect(readdirSync(dir)).not.toContain("codex-lb.key");
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });
});
