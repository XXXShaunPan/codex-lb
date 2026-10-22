import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuthStore } from "@/features/auth/hooks/use-auth";
import { get, put } from "@/lib/api-client";
import { PrioritySettings } from "./priority-settings";

const EntrySchema = z.object({
  accountId: z.string(), name: z.string(), kind: z.enum(["account", "model_source"]),
  weight: z.number().finite().min(0).max(1_000_000),
});
const WeightsSchema = z.object({ accounts: z.array(EntrySchema) });
type Entry = z.infer<typeof EntrySchema>;
const queryKey = ["relay-routing", "weights"];

function WeightRow({ entry, disabled }: { entry: Entry; disabled: boolean }) {
  const { t } = useTranslation();
  const client = useQueryClient();
  const [draft, setDraft] = useState(String(entry.weight));
  const [saved, setSaved] = useState(false);
  const value = Number(draft);
  const valid = draft.trim() !== "" && Number.isFinite(value) && value >= 0 && value <= 1_000_000;
  const mutation = useMutation({
    mutationFn: () => put(`/api/relay-routing/weights/${encodeURIComponent(entry.accountId)}`, z.object({ weight: z.number() }), { body: { weight: value } }),
    onSuccess: async () => { setSaved(true); await client.invalidateQueries({ queryKey }); },
  });
  return <div className="flex flex-wrap items-center gap-3 rounded-md border p-3">
    <div className="min-w-0 flex-1"><p className="truncate text-sm font-medium">{entry.name}</p>
      <p className="text-xs text-muted-foreground">{entry.kind === "model_source" ? "Model Source · other" : t("nav.accounts")}</p></div>
    <Input type="number" min={0} max={1_000_000} step="any" className="w-32"
      aria-label={t("settings.routing.weights.label", { name: entry.name })}
      value={draft} disabled={disabled || mutation.isPending}
      onChange={event => { setDraft(event.target.value); setSaved(false); }} />
    <Button type="button" variant="outline" size="sm" disabled={disabled || mutation.isPending || !valid || value === entry.weight}
      onClick={() => mutation.mutate()}>{t("common.actions.save")}</Button>
    {!valid && <p className="w-full text-xs text-destructive" role="alert">{t("settings.routing.weights.invalid")}</p>}
    {mutation.error && <p className="w-full text-xs text-destructive" role="alert">{mutation.error.message}</p>}
    {saved && <span role="status" className="text-xs text-muted-foreground">{t("settings.routing.weights.saved")}</span>}
  </div>;
}

export function RoutingWeightSettings({ accountId, disabled = false }: { accountId?: string; disabled?: boolean }) {
  const { t } = useTranslation();
  const canWrite = useAuthStore(state => state.canWrite);
  const query = useQuery({
    queryKey, queryFn: () => get("/api/relay-routing/weights", WeightsSchema),
    enabled: canWrite, staleTime: 15_000,
  });
  if (!canWrite) return null;
  const entries = query.data?.accounts.filter(entry => !accountId || entry.accountId === accountId) ?? [];
  return <><section className="space-y-3 rounded-lg border p-3">
    <h3 className="text-sm font-semibold">{t("settings.routing.weights.title")}</h3>
    <p className="text-xs text-muted-foreground">{t("settings.routing.weights.description")}</p>
    {query.isPending && <p className="text-xs">{t("common.loading")}</p>}
    {query.error && <p role="alert" className="text-xs text-destructive">{query.error.message}</p>}
    {entries.map(entry => <WeightRow key={`${entry.accountId}:${entry.weight}`} entry={entry} disabled={disabled} />)}
  </section><PrioritySettings accountId={accountId} disabled={disabled} /></>;
}
