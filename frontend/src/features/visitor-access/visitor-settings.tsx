import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { listApiKeys } from "@/features/api-keys/api";
import { relayRequest, type Visitor } from "./api";

type Draft = Omit<Visitor, "id"> & { password: string; id?: string };
const emptyDraft: Draft = { username: "", displayName: "", active: true, apiKeyIds: [], password: "" };

export function VisitorSettings() {
  const { i18n } = useTranslation();
  const zh = i18n.language.startsWith("zh");
  const client = useQueryClient();
  const visitors = useQuery({ queryKey: ["relay", "visitors"], queryFn: () => relayRequest<{visitors: Visitor[]}>("/api/visitor/admin/visitors") });
  const keys = useQuery({ queryKey: ["api-keys", "list"], queryFn: listApiKeys });
  const [draft, setDraft] = useState<Draft | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const refresh = () => client.invalidateQueries({ queryKey: ["relay", "visitors"] });
  return <section className="space-y-4 rounded-xl border bg-card p-5">
    <div className="flex items-center justify-between"><h3 className="font-semibold">{zh ? "访客列表" : "Visitors"}</h3>
      <Button onClick={() => { setError(null); setDraft({ ...emptyDraft }); }}>{zh ? "添加访客" : "Add visitor"}</Button></div>
    {visitors.error && <p role="alert">{visitors.error.message}</p>}
    {error && <p role="alert" className="text-destructive">{error}</p>}
    {(visitors.data?.visitors ?? []).map(visitor => <div key={visitor.id} className="flex flex-wrap items-center gap-3 border-t pt-3">
      <div className="min-w-0 flex-1"><p className="font-medium">{visitor.displayName} <span className="text-muted-foreground">({visitor.username})</span></p>
        <p className="text-sm text-muted-foreground">{visitor.active ? (zh ? "启用" : "Active") : (zh ? "停用" : "Disabled")} · {visitor.apiKeyIds.map(id => keys.data?.find(k => k.id === id)?.name ?? id).join(", ") || (zh ? "未分配 Key" : "No keys assigned")}</p></div>
      <Button variant="outline" onClick={() => { setError(null); setDraft({ ...visitor, password: "" }); }}>{zh ? "编辑与分配" : "Edit assignments"}</Button>
      <Button variant="destructive" disabled={busy} onClick={async () => {
        if (!window.confirm(zh ? `删除访客 ${visitor.username}？` : `Delete visitor ${visitor.username}?`)) return;
        setBusy(true); setError(null);
        try { await relayRequest(`/api/visitor/admin/visitors/${visitor.id}`, { method: "DELETE" }); await refresh(); }
        catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
        finally { setBusy(false); }
      }}>{zh ? "删除" : "Delete"}</Button>
    </div>)}
    <Dialog open={draft !== null} onOpenChange={(open) => { if (!open) setDraft(null); }}><DialogContent className="max-h-[85vh] overflow-y-auto">
      <DialogTitle>{zh ? "访客与 API Key 授权" : "Visitor and API key assignments"}</DialogTitle>
      <DialogDescription>{zh ? "访客只能查看所分配 Key 的用量。" : "Visitors can only view usage for assigned keys."}</DialogDescription>
      {draft && <form className="space-y-3" onSubmit={async e => {
        e.preventDefault(); setBusy(true); setError(null);
        try {
          await relayRequest(`/api/visitor/admin/visitors${draft.id ? `/${draft.id}` : ""}`, {
            method: draft.id ? "PATCH" : "POST", body: JSON.stringify(draft),
          });
          setDraft(null); await refresh();
        } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
        finally { setBusy(false); }
      }}>
        <label className="block text-sm">{zh ? "账号" : "Username"}<Input required value={draft.username} onChange={e => setDraft({...draft, username:e.target.value})} /></label>
        <label className="block text-sm">{zh ? "显示名称" : "Display name"}<Input value={draft.displayName} onChange={e => setDraft({...draft, displayName:e.target.value})} /></label>
        <label className="block text-sm">{zh ? "密码（编辑时留空保留）" : "Password (leave blank to keep)"}<Input type="password" autoComplete="new-password" minLength={8} required={!draft.id} value={draft.password} onChange={e => setDraft({...draft, password:e.target.value})} /></label>
        <label className="flex gap-2"><input type="checkbox" checked={draft.active} onChange={e => setDraft({...draft, active:e.target.checked})}/>{zh ? "启用" : "Active"}</label>
        <fieldset className="space-y-2"><legend>{zh ? "分配 API Key" : "Assign API keys"}</legend>
          {keys.data?.map(key => <label key={key.id} className="flex gap-2"><input type="checkbox" checked={draft.apiKeyIds.includes(key.id)} onChange={e => setDraft({...draft, apiKeyIds:e.target.checked ? [...draft.apiKeyIds,key.id] : draft.apiKeyIds.filter(id => id!==key.id)})}/>{key.name}</label>)}
        </fieldset>
        {error && <p role="alert" className="text-destructive">{error}</p>}
        <Button disabled={busy} type="submit">{zh ? "保存" : "Save"}</Button>
      </form>}
    </DialogContent></Dialog>
  </section>;
}
