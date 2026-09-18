import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { ModelSourceEditDialog } from "@/features/model-sources/components/model-source-edit-dialog";
import { useModelSources } from "@/features/model-sources/hooks/use-model-sources";

export function SourceAccountDetail({ sourceId }: { sourceId: string }) {
  const { t, i18n } = useTranslation();
  const zh = i18n.language.startsWith("zh");
  const { modelSourcesQuery, updateMutation, deleteMutation } = useModelSources();
  const [edit, setEdit] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const source = modelSourcesQuery.data?.sources.find(item => item.id === sourceId);
  if (!source) return <div className="rounded-xl border p-5">{modelSourcesQuery.error?.message ?? t("common.loading")}</div>;
  const busy = updateMutation.isPending || deleteMutation.isPending;
  return <section className="space-y-4 rounded-xl border bg-card p-5">
    <h2 className="text-lg font-semibold">{source.name}</h2>
    <p className="text-sm text-muted-foreground">other · {zh ? "每周剩余 100% · 无 5 小时额度" : "100% weekly remaining · no 5-hour quota"}</p>
    <p className="break-all text-sm">{source.baseUrl}</p>
    <div className="flex flex-wrap gap-2">{source.models.map(model => <span key={model.id} className="rounded border px-2 py-1 text-xs">{model.model}</span>)}</div>
    <p className="text-sm text-muted-foreground">{zh ? "已收录模型按账号池价格结算，包含缓存与长上下文费率。" : "Catalog models use account-pool rates, including cached input and long context."}</p>
    {(updateMutation.error || deleteMutation.error) && <p role="alert" className="text-destructive">{updateMutation.error?.message ?? deleteMutation.error?.message}</p>}
    <div className="flex flex-wrap gap-2">
      <Button disabled={busy} variant="outline" onClick={() => setEdit(true)}>{t("common.actions.edit")}</Button>
      <Button disabled={busy} variant="outline" onClick={() => updateMutation.mutate({ sourceId, payload:{isEnabled:!source.isEnabled} })}>{source.isEnabled ? t("common.actions.disable") : t("common.actions.enable")}</Button>
      <Button disabled={busy} variant="destructive" onClick={() => setConfirmDelete(true)}>{t("common.actions.delete")}</Button>
    </div>
    <ModelSourceEditDialog source={source} open={edit} busy={busy} onOpenChange={setEdit}
      onSubmit={async (id, payload) => { await updateMutation.mutateAsync({sourceId:id,payload}); }} />
    <ConfirmDialog open={confirmDelete} onOpenChange={setConfirmDelete} title={t("common.actions.delete")}
      description={zh ? `删除 ${source.name}？历史请求记录保留。` : `Delete ${source.name}? Request history is retained.`}
      onConfirm={() => { void deleteMutation.mutateAsync(sourceId).then(() => setConfirmDelete(false)); }} />
  </section>;
}
