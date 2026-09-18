import {describe,expect,it} from "vitest";
import {buildBashCodexCommand,buildWindowsCodexCommand,buildCodexRestoreCommands} from "./commands";

describe("relay Codex configuration",()=>{
  it("backs up configuration and key before replacing either on POSIX",()=>{
    const command=buildBashCodexCommand("sk-test'quote","gpt-6-astra","http://localhost:8080/backend-api/codex");
    expect(command.indexOf('cp -p "$CONFIG"')).toBeLessThan(command.indexOf('> "$CONFIG"'));
    expect(command.indexOf('cp -p "$KEY_FILE"')).toBeLessThan(command.indexOf('> "$KEY_FILE"'));
    expect(command).toContain("'\"'\"'");
    expect(command).toContain("chmod 600");
    expect(command).toContain("supports_websockets = false");
  });
  it("backs up configuration and uses a protected key file on Windows",()=>{
    const command=buildWindowsCodexCommand("sk-test","gpt-6-astra","http://localhost:8080/backend-api/codex");
    expect(command.indexOf("Copy-Item -LiteralPath $config")).toBeLessThan(command.indexOf("WriteAllText($config"));
    expect(command).toContain("icacls $keyFile");
    expect(command).toContain("$env:CODEX_HOME");
    expect(buildCodexRestoreCommands().windows).toContain("before-restore");
    expect(buildCodexRestoreCommands().linux).toContain("before-restore");
  });
});
