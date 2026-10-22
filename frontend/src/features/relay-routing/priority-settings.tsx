import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuthStore } from "@/features/auth/hooks/use-auth";
import { get, put } from "@/lib/api-client";

const PriorityRuleSchema = z.object({
  normalPriority: z.number().int().min(0).max(10000),
  lowPriority: z.number().int().min(0).max(10000),
  downgradePercent: z.number().min(0).lt(100),
  recoveryPercent: z.number().gt(0).max(100),
  quotaBasis: z.enum(["weekly", "five_hour", "minimum"]),
  allowLowQuota: z.boolean(),
}).refine(rule => rule.recoveryPercent > rule.downgradePercent);
type Rule = z.infer<typeof PriorityRuleSchema>;
const RulesSchema = z.object({
  plans: z.array(z.object({ planType: z.string(), rule: PriorityRuleSchema })),
  accounts: z.array(z.object({
    accountId: z.string(), name: z.string(), planType: z.string(),
    override: PriorityRuleSchema.nullable(), effectiveRule: PriorityRuleSchema,
    quotaPlaceholder: z.boolean(),
  })),
});
type AccountRule = z.infer<typeof RulesSchema>["accounts"][number];
const queryKey = ["relay-routing", "rules"];
const tr = "settings.routing.priority.";

function RuleFields({ value, onChange, disabled, name }: {
  value: Rule; onChange: (rule: Rule) => void; disabled: boolean; name: string;
}) {
  const { t } = useTranslation();
  const numeric = ["normalPriority", "lowPriority", "downgradePercent", "recoveryPercent"] as const;
  return <div className="grid gap-3 sm:grid-cols-2">
    {numeric.map(field => <label key={field} className="space-y-1 text-xs">
      <span>{t(tr + field)}</span>
      <Input type="number" min={0} max={field.endsWith("Priority") ? 10000 : 100}
        step={field.endsWith("Priority") ? 1 : "any"}
        value={Number.isNaN(value[field]) ? "" : value[field]} disabled={disabled}
        aria-label={`${name} · ${t(tr + field)}`}
        onChange={event => onChange({ ...value, [field]: event.target.value === "" ? NaN : Number(event.target.value) })} />
    </label>)}
    <label className="space-y-1 text-xs">
      <span>{t(tr + "quotaBasis")}</span>
      <select className="h-9 w-full rounded-md border bg-background px-2" disabled={disabled}
        aria-label={`${name} · ${t(tr + "quotaBasis")}`} value={value.quotaBasis}
        onChange={event => onChange({ ...value, quotaBasis: event.target.value as Rule["quotaBasis"] })}>
        {["weekly", "five_hour", "minimum"].map(basis => <option key={basis} value={basis}>{t(tr + basis)}</option>)}
      </select>
    </label>
    <label className="flex items-center gap-2 text-xs">
      <input type="checkbox" checked={value.allowLowQuota} disabled={disabled}
        aria-label={`${name} · ${t(tr + "allowLowQuota")}`}
        onChange={event => onChange({ ...value, allowLowQuota: event.target.checked })} />
      {t(tr + "allowLowQuota")}
    </label>
  </div>;
}

function PlanEditor({ plan, rule, disabled }: { plan: string; rule: Rule; disabled: boolean }) {
  const { t } = useTranslation();
  const client = useQueryClient();
  const [draft, setDraft] = useState(rule);
  const mutation = useMutation({
    mutationFn: () => put(`/api/relay-routing/rules/plans/${encodeURIComponent(plan)}`, PriorityRuleSchema, { body: draft }),
    onSuccess: () => client.invalidateQueries({ queryKey }),
  });
  const valid = PriorityRuleSchema.safeParse(draft).success;
  return <div className="space-y-3 rounded-md border p-3">
    <RuleFields value={draft} onChange={setDraft} disabled={disabled || mutation.isPending} name={plan} />
    {!valid && <p role="alert" className="text-xs text-destructive">{t(tr + "invalid")}</p>}
    {mutation.error && <p role="alert" className="text-xs text-destructive">{mutation.error.message}</p>}
    <Button size="sm" disabled={disabled || mutation.isPending || !valid}
      onClick={() => mutation.mutate()}>{t(tr + "savePlan")}</Button>
    {mutation.isSuccess && <span role="status" className="ml-3 text-xs">{t("settings.routing.weights.saved")}</span>}
  </div>;
}

function AccountEditor({ entry, disabled }: { entry: AccountRule; disabled: boolean }) {
  const { t } = useTranslation();
  const client = useQueryClient();
  const [override, setOverride] = useState(entry.override !== null);
  const [draft, setDraft] = useState(entry.effectiveRule);
  const mutation = useMutation({
    mutationFn: () => put(`/api/relay-routing/rules/accounts/${encodeURIComponent(entry.accountId)}`,
      z.object({ override: PriorityRuleSchema.nullable() }), { body: { override: override ? draft : null } }),
    onSuccess: () => client.invalidateQueries({ queryKey }),
  });
  const valid = !override || PriorityRuleSchema.safeParse(draft).success;
  return <details className="rounded-md border p-3">
    <summary className="cursor-pointer text-sm">{entry.name} · {entry.planType} · {t(tr + (entry.override ? "custom" : "inherited"))}</summary>
    <div className="mt-3 space-y-3">
      <p className="text-xs text-muted-foreground">{t(tr + (entry.quotaPlaceholder ? "placeholder" : "unknown"))}</p>
      <label className="flex items-center gap-2 text-xs">
        <input type="checkbox" checked={override} disabled={disabled || mutation.isPending}
          aria-label={`${entry.name} · ${t(tr + "override")}`}
          onChange={event => setOverride(event.target.checked)} />{t(tr + "override")}
      </label>
      <RuleFields value={draft} onChange={setDraft} name={entry.name}
        disabled={disabled || mutation.isPending || !override} />
      {!valid && <p role="alert" className="text-xs text-destructive">{t(tr + "invalid")}</p>}
      {mutation.error && <p role="alert" className="text-xs text-destructive">{mutation.error.message}</p>}
      <Button size="sm" disabled={disabled || mutation.isPending || !valid}
        onClick={() => mutation.mutate()}>{t(tr + "saveAccount")}</Button>
      {mutation.isSuccess && <span role="status" className="ml-3 text-xs">{t("settings.routing.weights.saved")}</span>}
    </div>
  </details>;
}

export function PrioritySettings({ accountId, disabled = false }: { accountId?: string; disabled?: boolean }) {
  const { t } = useTranslation();
  const canWrite = useAuthStore(state => state.canWrite);
  const [plan, setPlan] = useState("plus");
  const query = useQuery({ queryKey, queryFn: () => get("/api/relay-routing/rules", RulesSchema), enabled: canWrite });
  if (!canWrite) return null;
  const selected = query.data?.plans.find(entry => entry.planType === plan);
  return <section className="space-y-3 rounded-lg border p-3">
    <h3 className="text-sm font-semibold">{t(tr + "title")}</h3>
    <p className="text-xs text-muted-foreground">{t(tr + "description")}</p>
    {query.isPending && <p className="text-xs">{t("common.loading")}</p>}
    {query.error && <p role="alert" className="text-xs text-destructive">{query.error.message}</p>}
    {!accountId && <>
      <label className="flex items-center gap-3 text-sm">{t(tr + "plan")}
        <select className="h-9 rounded-md border bg-background px-2" value={plan}
          aria-label={t(tr + "plan")} disabled={disabled} onChange={event => setPlan(event.target.value)}>
          {query.data?.plans.map(entry => <option key={entry.planType} value={entry.planType}>
            {entry.planType === "*" ? t(tr + "otherPlans") : entry.planType}
          </option>)}
        </select>
      </label>
      {selected && <PlanEditor key={plan + JSON.stringify(selected.rule)} plan={plan} rule={selected.rule} disabled={disabled} />}
    </>}
    {query.data?.accounts.filter(entry => !accountId || entry.accountId === accountId).map(entry =>
      <AccountEditor key={entry.accountId + JSON.stringify([entry.override, entry.effectiveRule])} entry={entry} disabled={disabled} />)}
  </section>;
}
