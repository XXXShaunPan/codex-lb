/// <reference types="node" />
import {
  existsSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { describe, expect, it } from "vitest";
import {
  buildBashCodexCommand,
  buildWindowsCodexCommand,
  buildBashRestoreCommand,
  buildWindowsRestoreCommand,
  buildCodexCommands,
} from "./commands";

const token = "sk-clb-test-'\"$\\-中文";
const baseUrl = "https://relay.example.test:8443/backend-api/codex";
const windows = process.platform === "win32";
const bash = windows ? "C:/Program Files/Git/bin/bash.exe" : "/bin/bash";
const runtimes = [
  ...(windows ? ["powershell"] : []),
  ...(existsSync(bash) ? ["posix"] : []),
];
const python =
  process.env.RELAY_TEST_PYTHON ??
  (existsSync(
    resolve("../.venv", windows ? "Scripts/python.exe" : "bin/python"),
  )
    ? resolve("../.venv", windows ? "Scripts/python.exe" : "bin/python")
    : windows
      ? "python"
      : "python3");
function parseToml(text: string) {
  const result = spawnSync(
    python,
    [
      "-X",
      "utf8",
      "-c",
      "import tomllib,json,sys; print(json.dumps(tomllib.loads(sys.stdin.read())))",
    ],
    { input: text, encoding: "utf8" },
  );
  expect(result.status, result.stderr).toBe(0);
  return JSON.parse(result.stdout);
}
function unixPath(path: string) {
  return windows
    ? path
        .replace(/\\/g, "/")
        .replace(
          /^([A-Za-z]):/,
          (_, drive: string) => "/" + drive.toLowerCase(),
        )
    : path;
}
function run(dir: string, runtime: string, cleanup = false) {
  const win = runtime === "powershell";
  const script = join(dir, win ? "run.ps1" : "run.sh");
  const command = win
    ? cleanup
      ? buildWindowsRestoreCommand(baseUrl)
      : buildWindowsCodexCommand(token, "gpt-6-astra", baseUrl)
    : cleanup
      ? buildBashRestoreCommand(baseUrl)
      : buildBashCodexCommand(token, "gpt-6-astra", baseUrl);
  expect(command).not.toMatch(
    /\b(python[23]?|node|pip|npx|curl|Invoke-WebRequest)\b/i,
  );
  writeFileSync(script, command);
  const env: NodeJS.ProcessEnv = { ...process.env, CODEX_HOME: win ? dir : unixPath(dir) };
  if (windows)
    env.PATH = win
      ? process.env.SystemRoot + "/System32"
      : "C:/Program Files/Git/usr/bin;" + process.env.SystemRoot + "/System32";
  return spawnSync(
    win
      ? process.env.SystemRoot +
          "/System32/WindowsPowerShell/v1.0/powershell.exe"
      : bash,
    win
      ? ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script]
      : [unixPath(script)],
    { env, encoding: "utf8", timeout: 30000 },
  );
}
const fixtures = [
  { name: "empty", text: "", provider: "openai_https" },
  {
    name: "active custom",
    text: 'model_provider="mine"\n[features]\nshell_tool=true\n[model_providers.mine]\nname="Old"\nenv_key="OLD"\n',
    provider: "mine",
  },
  {
    name: "dotted keys",
    text: 'model_providers.mine.name="Old"\nfeatures.shell_tool=true\n',
    provider: "mine",
  },
  {
    name: "quoted provider",
    text: 'model_provider="with.dot"\n[model_providers."with.dot"]\nname="Old"\n',
    provider: "with.dot",
  },
  {
    name: "escaped provider",
    text: 'model_provider="\\u006dine"\n[model_providers.mine]\nname="Old"\n',
    provider: "mine",
  },
  {
    name: "inline tables",
    text: 'model_providers={ mine={name="Old",http_headers={"X-Keep"="keep"}}, remote={name="Remote",base_url="https://other.test/v1",experimental_bearer_token="keep-other"} }\nmodel_provider="mine"\nfeatures={shell_tool=true}\n',
    provider: "mine",
  },
  {
    name: "nested headers",
    text: 'model_provider="mine"\n[model_providers.mine]\nname="Old"\n[model_providers.mine.http_headers]\nAuthorization="replace"\nX-OpenAI-Actor-Authorization="replace"\nX-Keep="keep"\n',
    provider: "mine",
  },
  {
    name: "existing discovery",
    text: "features.api_key_model_discovery=true\n",
    provider: "openai_https",
  },
  {
    name: "disabled discovery",
    text: "[features]\napi_key_model_discovery=false\n",
    provider: "openai_https",
  },
  {
    name: "BOM CRLF",
    text: '\ufeffmodel_provider="mine"\r\n[model_providers.mine]\r\nname="Old"\r\n',
    provider: "mine",
  },
  {
    name: "empty nested values",
    text: 'model_provider="mine"\n[model_providers.mine]\nname="Old"\nquery_params={}\nrequest_max_retries=7\n',
    provider: "mine",
  },
];
const unrelated =
  '\n# keep unrelated settings\n[projects."/my/project"]\ntrust_level="trusted"\nnote="""[model_providers.fake]\n# not a comment\nmodel_provider = \'not-a-provider\'"""\n[mcp_servers.local]\ncommand="my-tool"\nargs=["--flag", # preserve array semantics\n"two"]\n';

describe.each(runtimes)("native Codex editor (%s)", (runtime) => {
  it("removes legacy key-file auth fields without deleting credential files", () => {
    const dir = mkdtempSync(join(tmpdir(), "relay-legacy-"));
    try {
      writeFileSync(
        join(dir, "config.toml"),
        'model="keep-model"\nmodel_provider="codex_lb"\n[model_providers.codex_lb]\nname="Codex LB"\nbase_url="http://old-host/backend-api/codex"\nwire_api="responses"\n[model_providers.codex_lb.auth]\ncommand="sh"\nargs=["-c","cat codex-lb.key"]\n',
      );
      writeFileSync(join(dir, "codex-lb.key"), "keep-file");
      const result = run(dir, runtime, true);
      expect(result.status, result.stderr).toBe(0);
      expect(parseToml(readFileSync(join(dir, "config.toml"), "utf8"))).toEqual(
        { model: "keep-model" },
      );
      expect(readFileSync(join(dir, "codex-lb.key"), "utf8")).toBe("keep-file");
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });
  it.each(fixtures)(
    "preserves configuration and supports targeted cleanup: $name",
    (fixture) => {
      const dir = mkdtempSync(join(tmpdir(), "relay config 测试-"));
      try {
        const original = fixture.text + unrelated;
        const before = parseToml(original.replace(/^\ufeff/, ""));
        writeFileSync(join(dir, "config.toml"), original);
        const result = run(dir, runtime);
        expect(result.status, result.stderr).toBe(0);
        const configured = readFileSync(join(dir, "config.toml"), "utf8");
        const parsed = parseToml(configured);
        expect(parsed.model_provider).toBe(fixture.provider);
        expect(parsed.model).toBe("gpt-6-astra");
        expect(parsed.model_providers[fixture.provider]).toMatchObject({
          name: "OpenAI",
          base_url: baseUrl,
          model_catalog_url: baseUrl + "/models",
          wire_api: "responses",
          experimental_bearer_token: token,
          requires_openai_auth: true,
          http_headers: { "x-openai-actor-authorization": "codex-lb" },
        });
        expect(parsed.projects).toEqual(before.projects);
        expect(parsed.mcp_servers).toEqual(before.mcp_servers);
        expect(parsed.features.api_key_model_discovery).toBe(true);
        if (before.model_providers?.remote)
          expect(parsed.model_providers.remote).toEqual(
            before.model_providers.remote,
          );
        expect(
          parsed.model_providers[fixture.provider].env_key,
        ).toBeUndefined();
        const backups = () =>
          readdirSync(dir).filter((name) =>
            name.startsWith("config.toml.bak."),
          );
        expect(backups()).toHaveLength(1);
        expect(readFileSync(join(dir, backups()[0]), "utf8")).toBe(original);
        const repeat = run(dir, runtime);
        expect(repeat.status, repeat.stderr).toBe(0);
        expect(readFileSync(join(dir, "config.toml"), "utf8")).toBe(configured);
        expect(backups()).toHaveLength(1);
        const newer = configured + '\n[newer]\nkeep="added after setup"\n';
        writeFileSync(join(dir, "config.toml"), newer);
        writeFileSync(
          join(dir, "config.toml.bak.ancient"),
          'model="obsolete-backup"\n',
        );
        const cleaned = run(dir, runtime, true);
        expect(cleaned.status, cleaned.stderr).toBe(0);
        const afterText = readFileSync(join(dir, "config.toml"), "utf8");
        const after = parseToml(afterText);
        expect(after.model).toBe("gpt-6-astra");
        expect(after.model_provider).toBeUndefined();
        expect(after.newer.keep).toBe("added after setup");
        expect(after.projects).toEqual(before.projects);
        expect(after.mcp_servers).toEqual(before.mcp_servers);
        expect(
          after.model_providers?.[fixture.provider]?.base_url,
        ).toBeUndefined();
        expect(
          after.model_providers?.[fixture.provider]?.experimental_bearer_token,
        ).toBeUndefined();
        if (before.model_providers?.remote)
          expect(after.model_providers.remote).toEqual(
            before.model_providers.remote,
          );
        if (fixture.name === "empty nested values")
          expect(after.model_providers.mine).toMatchObject({
            query_params: {},
            request_max_retries: 7,
          });
        expect(after.features?.api_key_model_discovery).toBe(
          before.features?.api_key_model_discovery,
        );
        expect(
          after.model_providers?.[fixture.provider]?.http_headers?.[
            "x-openai-actor-authorization"
          ],
        ).toBeUndefined();
        if (
          fixture.name === "inline tables" ||
          fixture.name === "nested headers"
        )
          expect(
            after.model_providers[fixture.provider].http_headers["X-Keep"],
          ).toBe("keep");
        const count = backups().length;
        expect(run(dir, runtime, true).status).toBe(0);
        expect(readFileSync(join(dir, "config.toml"), "utf8")).toBe(afterText);
        expect(backups()).toHaveLength(count);
      } finally {
        rmSync(dir, { recursive: true, force: true });
      }
    },
    60000,
  );

  it("cleans legacy relay fields without restoring old backups or touching another provider", () => {
    const dir = mkdtempSync(join(tmpdir(), "relay-cleanup-"));
    const original =
      'model="my-model"\nmodel_provider="mine"\n[features]\napi_key_model_discovery=true\n[model_providers.mine]\nname="OpenAI"\nbase_url="http://old-host/backend-api/codex"\nexperimental_bearer_token="sk-clb-old"\nhttp_headers={x-openai-actor-authorization="codex-lb",X-Keep="keep"}\n[model_providers.other]\nname="Other"\nbase_url="https://other.test"\nexperimental_bearer_token="other-secret"\n[profiles.test]\nmodel_provider="mine"\nmodel="keep-profile"\n';
    try {
      writeFileSync(join(dir, "config.toml"), original);
      writeFileSync(join(dir, "auth.json"), '{"unchanged":true}');
      const result = run(dir, runtime, true);
      expect(result.status, result.stderr).toBe(0);
      const parsed = parseToml(readFileSync(join(dir, "config.toml"), "utf8"));
      expect(parsed.model).toBe("my-model");
      expect(parsed.model_provider).toBeUndefined();
      expect(parsed.model_providers.other).toEqual(
        parseToml(original).model_providers.other,
      );
      expect(parsed.profiles.test).toEqual({ model: "keep-profile" });
      expect(parsed.features.api_key_model_discovery).toBe(true);
      expect(readFileSync(join(dir, "auth.json"), "utf8")).toBe(
        '{"unchanged":true}',
      );
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  }, 60000);

  it.each([
    "",
    'model="keep"',
    'model_provider="openai_https"\n[model_providers.openai_https]\nname="Unrelated"\nbase_url="https://other.test/v1"\nexperimental_bearer_token="unrelated"',
  ])("leaves a non-relay config byte-for-byte unchanged", (original) => {
    const dir = mkdtempSync(join(tmpdir(), "relay-noop-"));
    try {
      writeFileSync(join(dir, "config.toml"), original);
      const result = run(dir, runtime, true);
      expect(result.status, result.stderr).toBe(0);
      expect(readFileSync(join(dir, "config.toml"), "utf8")).toBe(original);
      expect(
        readdirSync(dir).filter((name) => name.includes(".bak.")),
      ).toHaveLength(0);
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });

  it.each([
    "[features\n",
    'model_provider="unterminated\n',
    "[features]\na=true\n[features]\nb=false\n",
  ])("fails before overwriting structurally invalid input", (original) => {
    const dir = mkdtempSync(join(tmpdir(), "relay-invalid-"));
    try {
      writeFileSync(join(dir, "config.toml"), original);
      expect(run(dir, runtime).status).not.toBe(0);
      expect(readFileSync(join(dir, "config.toml"), "utf8")).toBe(original);
      expect(
        readdirSync(dir).filter((name) => name.includes(".bak.")),
      ).toHaveLength(0);
    } finally {
      rmSync(dir, { recursive: true, force: true });
    }
  });
});
it("uses the current website origin", () => {
  const commands = buildCodexCommands("sk-test", "gpt-6-astra");
  const payload = JSON.parse(
    Buffer.from(
      commands.windows.match(/FromBase64String\('([^']+)'\)/)![1],
      "base64",
    ).toString(),
  );
  expect(payload.base_url).toBe(location.origin + "/backend-api/codex");
  expect(commands.macos).toBe(commands.linux);
});
