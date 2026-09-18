import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import type { ApiKey } from "@/features/api-keys/schemas";
import { relayRequest } from "@/features/visitor-access/api";
import { buildCodexCommands, buildCodexRestoreCommands } from "./commands";

export function CodexConfigButton({ apiKeys }: { apiKeys: ApiKey[] }) {
  const { i18n } = useTranslation();
  const zh = i18n.language.startsWith("zh");
  const client = useQueryClient();
  const [open, setOpen] = useState(false);
  const [keyId, setKeyId] = useState("");
  const [model, setModel] = useState("gpt-6-astra");
  const [platform, setPlatform] = useState<"macos" | "linux" | "windows">("windows");
  const [confirmed, setConfirmed] = useState(false);
  const [commands, setCommands] = useState<Record<string, string> | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const activeKeys = apiKeys.filter(key => key.isActive);
  const selected = activeKeys.find(key => key.id === keyId) ?? activeKeys[0];
  const close = (value: boolean) => { setOpen(value); if (!value) { setCommands(null); setConfirmed(false); setError(null); setCopied(false); } };
  return <>
    <div className="flex flex-wrap gap-2">
      <Button disabled={!activeKeys.length} onClick={() => { setCommands(null); setOpen(true); }}>{zh ? "一键配置到 Codex" : "Configure Codex"}</Button>
      <Button variant="outline" onClick={() => { setCommands(buildCodexRestoreCommands()); setOpen(true); }}>{zh ? "恢复 Codex 配置" : "Restore Codex config"}</Button>
    </div>
    <Dialog open={open} onOpenChange={close}><DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
      <DialogTitle>{zh ? "Codex 配置" : "Codex configuration"}</DialogTitle>
      <DialogDescription>{zh ? "命令会备份原有 config.toml 与 Key 文件。执行后请完全退出并重启 Codex。" : "Commands back up config.toml and the key file. Fully restart Codex afterward."}</DialogDescription>
      <label className="text-sm">{zh ? "操作系统" : "Operating system"}<select className="ml-2 rounded border bg-background p-2" value={platform} onChange={e => setPlatform(e.target.value as typeof platform)}>
        <option value="macos">macOS (Bash)</option><option value="linux">Linux (Bash)</option><option value="windows">Windows (PowerShell)</option>
      </select></label>
      {!commands ? <div className="space-y-4">
        <label className="block text-sm">API Key<select className="mt-1 block w-full rounded border bg-background p-2" value={selected?.id ?? ""} onChange={e => setKeyId(e.target.value)}>{activeKeys.map(key => <option key={key.id} value={key.id}>{key.name}</option>)}</select></label>
        <label className="block text-sm">{zh ? "模型" : "Model"}<Input value={model} onChange={e => setModel(e.target.value)} /></label>
        <label className="flex items-start gap-2 rounded border border-amber-500/40 bg-amber-500/10 p-3 text-sm"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />
          {zh ? "我确认：生成命令将立即重置此 API Key，所有使用旧 Key 的配置都会失效。" : "I confirm: generating commands immediately resets this API key. All configurations using the old key will stop working."}</label>
        {location.protocol === "http:" && <p className="text-xs text-amber-600">{zh ? "当前使用 HTTP，请仅在可信网络传递此命令。" : "This page uses HTTP. Only transfer this command over a trusted network."}</p>}
        <Button disabled={busy || !confirmed || !selected || !model.trim()} onClick={async () => {
          if (!selected) return;
          setBusy(true); setError(null);
          try {
            const result = await relayRequest<{apiKey:{key:string}}>("/api/codex-config/regenerate", {method:"POST",body:JSON.stringify({apiKeyId:selected.id,confirmReset:true})});
            setCommands(buildCodexCommands(result.apiKey.key, model.trim()));
            await client.invalidateQueries({queryKey:["api-keys"]});
          } catch (cause) {setError(cause instanceof Error ? cause.message : String(cause));}
          finally {setBusy(false);}
        }}>{zh ? "重置并生成命令" : "Reset and generate commands"}</Button>
      </div> : <div className="space-y-3">
        <textarea aria-label={zh ? "配置命令" : "Configuration command"} className="h-72 w-full rounded border bg-muted p-3 font-mono text-xs" readOnly value={commands[platform]} />
        <Button onClick={async () => {try { await navigator.clipboard.writeText(commands[platform]); setCopied(true); } catch { setError(zh ? "请手动复制命令。" : "Please copy the command manually."); }}}>{copied ? (zh ? "已复制" : "Copied") : (zh ? "复制命令" : "Copy command")}</Button>
        <p className="text-sm">{zh ? "关闭后不再显示新 Key。执行后请完全退出并重启 Codex。" : "The new key will not be displayed again after closing. Fully restart Codex after running the command."}</p>
      </div>}
      {error && <p role="alert" className="text-destructive">{error}</p>}
    </DialogContent></Dialog>
  </>;
}
