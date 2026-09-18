import { useTranslation } from "react-i18next";

import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { MiniQuotaBar } from "@/components/mini-quota-bar";
import type { ApiKey } from "@/features/api-keys/schemas";
import { formatPercentNullable } from "@/utils/formatters";

export type ApiListItemProps = {
  apiKey: ApiKey;
  selected: boolean;
  onSelect: (keyId: string) => void;
};

function formatLimitPercent(apiKey: ApiKey): number | null {
  if (apiKey.limits.length === 0) return 0;
  let maxPercent = 0;
  for (const limit of apiKey.limits) {
    if (limit.maxValue > 0) {
      const pct = (limit.currentValue / limit.maxValue) * 100;
      if (pct > maxPercent) maxPercent = pct;
    }
  }
  return maxPercent;
}

function isExpired(apiKey: ApiKey): boolean {
  if (!apiKey.expiresAt) return false;
  return new Date(apiKey.expiresAt).getTime() < Date.now();
}

export function ApiListItem({ apiKey, selected, onSelect }: ApiListItemProps) {
  const { t } = useTranslation();
  const expired = isExpired(apiKey);
  const limitPct = formatLimitPercent(apiKey);

  return (
    <button
      type="button"
      onClick={() => onSelect(apiKey.id)}
      className={cn(
        "w-full rounded-lg px-3 py-2.5 text-left transition-colors",
        selected
          ? "bg-primary/8 ring-1 ring-primary/25"
          : "hover:bg-muted/50",
      )}
    >
      <div className="flex items-center gap-2.5">
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">{apiKey.name}</p>
        </div>
        <Badge
          className={cn(
            !apiKey.isActive || expired
              ? "bg-zinc-500 text-white"
              : "bg-emerald-500 text-white",
          )}
        >
          {!apiKey.isActive ? t("common.states.disabled") : expired ? t("common.states.expired") : t("common.states.active")}
        </Badge>
      </div>
      {limitPct !== null ? (
        <div className="mt-1.5 space-y-1">
          <div className="flex items-center justify-between text-[11px]">
            <span className="text-muted-foreground">API_KEY remaining quota</span>
            <span className="tabular-nums font-medium">{formatPercentNullable(Math.max(0, 100 - limitPct))}</span>
          </div>
          <MiniQuotaBar testId="api-key-remaining-quota" aria-label="API_KEY remaining quota" percent={Math.max(0, 100 - limitPct)} />
        </div>
      ) : null}
    </button>
  );
}
