import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import type { ApiKey } from "@/features/api-keys/schemas";
import { relayRequest } from "@/features/visitor-access/api";
import { buildCodexCommands, buildCodexRestoreCommands } from "./commands";

export function CodexConfigButton({ apiKeys }: { apiKeys: ApiKey[] }) {
  const { i18n } = useTranslation();
  const zh = i18n.language.startsWith("zh");
  const client = useQueryClient();
  const [open, setOpen] = useState(false);
  const [operation, setOperation] = useState<"setup" | "cleanup">("setup");
  const [keyId, setKeyId] = useState("");
  const [model, setModel] = useState("gpt-6-astra");
  const [platform, setPlatform] = useState<"macos" | "linux" | "windows">(
    "windows",
  );
  const [confirmed, setConfirmed] = useState(false);
  const [resetRequested, setResetRequested] = useState(false);
  const [commands, setCommands] = useState<Record<string, string> | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const activeKeys = apiKeys.filter((key) => key.isActive);
  const selected = activeKeys.find((key) => key.id === keyId) ?? activeKeys[0];
  const tokenStatus = useQuery({
    queryKey: ["codex-config-status", selected?.id, selected?.keyPrefix],
    queryFn: () =>
      relayRequest<{ tokenAvailable: boolean; resetRequired: boolean }>(
        `/api/codex-config/status?apiKeyId=${encodeURIComponent(selected!.id)}`,
      ),
    enabled: open && !commands && !!selected,
    staleTime: 0,
    retry: false,
  });
  const resetRequired = tokenStatus.data?.resetRequired === true;
  const willReset = resetRequired || resetRequested;
  const close = (value: boolean) => {
    setOpen(value);
    if (!value) {
      setCommands(null);
      setConfirmed(false);
      setResetRequested(false);
      setError(null);
      setCopied(false);
    }
  };
  return (
    <>
      <div className="flex flex-wrap gap-2">
        <Button
          disabled={!activeKeys.length}
          onClick={() => {
            setOperation("setup");
            setCommands(null);
            setOpen(true);
          }}
        >
          {zh ? "一键配置到 Codex" : "Configure Codex"}
        </Button>
        <Button
          variant="outline"
          onClick={() => {
            setOperation("cleanup");
            setCommands(buildCodexRestoreCommands());
            setOpen(true);
          }}
        >
          {zh ? "恢复 Codex 配置" : "Restore Codex config"}
        </Button>
      </div>
      <Dialog open={open} onOpenChange={close}>
        <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
          <DialogTitle>
            {operation === "cleanup"
              ? zh
                ? "移除 Codex-LB 配置"
                : "Remove Codex-LB settings"
              : zh
                ? "Codex 配置"
                : "Codex configuration"}
          </DialogTitle>
          <DialogDescription>
            {operation === "cleanup"
              ? zh
                ? "无需 Python。先备份当前配置，再仅移除 Codex-LB 的地址、token、专用请求头及关联 Provider 选择；保留模型、MCP、项目和其他 Provider，不使用旧备份覆盖，也不重置 API Key。"
                : "No Python required. Backs up the current file, then removes only Codex-LB URLs, token, actor header and provider selectors. Keeps models, MCP, projects and other providers; does not restore an old backup or reset any API key."
              : zh
                ? "使用系统自带 Shell/awk 或 PowerShell，无需 Python。先备份 config.toml，再更新 Provider 与模型发现，token 直接保存在配置中。执行后请重启 Codex。"
                : "Uses system shell/awk or PowerShell; no Python required. Backs up config.toml, updates the provider and model discovery, and saves the token inline. Restart Codex afterward."}
          </DialogDescription>
          <label className="text-sm">
            {zh ? "操作系统" : "Operating system"}
            <select
              className="ml-2 rounded border bg-background p-2"
              value={platform}
              onChange={(e) => setPlatform(e.target.value as typeof platform)}
            >
              <option value="macos">macOS (Bash)</option>
              <option value="linux">Linux (Bash)</option>
              <option value="windows">Windows (PowerShell)</option>
            </select>
          </label>
          {!commands ? (
            <div className="space-y-4">
              <label className="block text-sm">
                API Key
                <select
                  className="mt-1 block w-full rounded border bg-background p-2"
                  value={selected?.id ?? ""}
                  onChange={(e) => {
                    setKeyId(e.target.value);
                    setConfirmed(false);
                    setResetRequested(false);
                  }}
                >
                  {activeKeys.map((key) => (
                    <option key={key.id} value={key.id}>
                      {key.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-sm">
                {zh ? "模型" : "Model"}
                <Input
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                />
              </label>
              {resetRequired ? (
                <p className="rounded border border-amber-500/40 bg-amber-500/10 p-3 text-sm">
                  {zh
                    ? "此 Key 尚未保存可用 token，首次生成配置需要重置；后续可直接复用。"
                    : "No saved token exists for this key. The first configuration requires a reset; later exports can reuse it."}
                </p>
              ) : (
                <label className="flex gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={resetRequested}
                    onChange={(e) => {
                      setResetRequested(e.target.checked);
                      setConfirmed(false);
                    }}
                  />
                  {zh ? "重新生成 API Key（可选）" : "Reset API key (optional)"}
                </label>
              )}
              {willReset && (
                <label className="flex items-start gap-2 rounded border border-amber-500/40 bg-amber-500/10 p-3 text-sm">
                  <input
                    type="checkbox"
                    checked={confirmed}
                    onChange={(e) => setConfirmed(e.target.checked)}
                  />
                  {zh
                    ? "我确认重置此 Key，所有使用旧 token 的配置都将失效。"
                    : "I confirm resetting this key. All configurations using the old token will stop working."}
                </label>
              )}
              {tokenStatus.error && (
                <p role="alert" className="text-destructive">
                  {tokenStatus.error.message}
                </p>
              )}
              {location.protocol === "http:" && (
                <p className="text-xs text-amber-600">
                  {zh
                    ? "当前使用 HTTP，请仅在可信网络传递此命令。"
                    : "This page uses HTTP. Only transfer this command over a trusted network."}
                </p>
              )}
              <Button
                disabled={
                  busy ||
                  (willReset && !confirmed) ||
                  !selected ||
                  !model.trim() ||
                  !tokenStatus.data ||
                  tokenStatus.isFetching ||
                  !!tokenStatus.error
                }
                onClick={async () => {
                  if (!selected) return;
                  setBusy(true);
                  setError(null);
                  try {
                    const result = await relayRequest<{
                      apiKey: { key: string };
                      reset: boolean;
                    }>("/api/codex-config/generate", {
                      method: "POST",
                      body: JSON.stringify({
                        apiKeyId: selected.id,
                        resetKey: resetRequested,
                        confirmReset: confirmed,
                      }),
                    });
                    setCommands(
                      buildCodexCommands(result.apiKey.key, model.trim()),
                    );
                    await client.invalidateQueries({ queryKey: ["api-keys"] });
                  } catch (cause) {
                    setError(
                      cause instanceof Error ? cause.message : String(cause),
                    );
                    void tokenStatus.refetch();
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                {willReset
                  ? zh
                    ? "重置并生成命令"
                    : "Reset and generate commands"
                  : zh
                    ? "生成配置命令"
                    : "Generate configuration"}
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              <textarea
                aria-label={zh ? "配置命令" : "Configuration command"}
                className="h-72 w-full rounded border bg-muted p-3 font-mono text-xs"
                readOnly
                value={commands[platform]}
              />
              <Button
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(commands[platform]);
                    setCopied(true);
                  } catch {
                    setError(
                      zh
                        ? "请手动复制命令。"
                        : "Please copy the command manually.",
                    );
                  }
                }}
              >
                {copied
                  ? zh
                    ? "已复制"
                    : "Copied"
                  : zh
                    ? "复制命令"
                    : "Copy command"}
              </Button>
              <p className="text-sm">
                {operation === "cleanup"
                  ? zh
                    ? "执行后请完全退出并重启 Codex；原有登录文件不会被修改。"
                    : "Fully restart Codex afterward. Your existing login file is not modified."
                  : zh
                    ? "可再次生成配置并复用已保存的 Key。执行命令后请完全退出并重启 Codex。"
                    : "You can generate this configuration again using the saved key. Fully restart Codex after running it."}
              </p>
            </div>
          )}
          {error && (
            <p role="alert" className="text-destructive">
              {error}
            </p>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
