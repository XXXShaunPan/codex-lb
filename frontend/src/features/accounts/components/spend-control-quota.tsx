import { useTranslation } from "react-i18next";
import type { AccountSummary } from "@/features/accounts/schemas";
import { useDateDisplayFormatStore } from "@/hooks/use-date-format";
import { useSmoothPercent } from "@/hooks/use-smooth-percent";
import {
  formatDateTimeInline,
  formatPercentNullable,
} from "@/utils/formatters";
import { quotaBarColor } from "@/utils/account-status";
import { cn } from "@/lib/utils";

type Budget = NonNullable<AccountSummary["spendControl"]>;

export function SpendControlQuota({ budget }: { budget: Budget }) {
  const { i18n } = useTranslation();
  const zh = i18n.language.startsWith("zh");
  const dateFormat = useDateDisplayFormatStore((s) => s.dateDisplayFormat);
  const { percent } = useSmoothPercent(budget.remainingPercent);
  const unit = budget.unit?.toUpperCase() ?? "—";
  const amount = (value: string | null) => {
    if (value === null) return "—";
    const numeric = Number(value);
    return Number.isFinite(numeric)
      ? numeric.toLocaleString(i18n.language, { maximumFractionDigits: 2 })
      : "—";
  };
  const exhausted =
    budget.reached === true ||
    (budget.remaining !== null && Number(budget.remaining) <= 0);
  return (
    <div
      className="col-span-full space-y-1.5 text-xs"
      data-testid="spend-control-quota"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="font-medium">
          {zh ? "支出额度" : "Spending budget"} ({unit})
        </span>
        <span className="tabular-nums">
          {formatPercentNullable(percent, 1)}
        </span>
      </div>
      {percent !== null && (
        <div className="h-1.5 overflow-hidden rounded-full bg-muted">
          <div
            className={cn("h-full rounded-full", quotaBarColor(percent))}
            style={{ width: `${percent}%` }}
          />
        </div>
      )}
      <div className="flex flex-wrap gap-x-3 gap-y-1 tabular-nums text-muted-foreground">
        <span>
          {zh ? "剩余" : "Remaining"}: {amount(budget.remaining)}
        </span>
        <span>
          {zh ? "已用" : "Used"}: {amount(budget.used)}
        </span>
        <span>
          {zh ? "上限" : "Limit"}: {amount(budget.limit)}
        </span>
      </div>
      {exhausted && (
        <p className="text-destructive">
          {zh
            ? "预算已达上限，等待上游额度更新"
            : "Budget exhausted; awaiting updated upstream allowance"}
        </p>
      )}
      <p className="text-[11px] text-muted-foreground">
        {zh ? "重置" : "Resets"}:{" "}
        {budget.resetAt
          ? formatDateTimeInline(budget.resetAt, dateFormat)
          : "—"}
      </p>
      <p className="text-[11px] text-muted-foreground">
        {zh ? "更新于" : "Updated"}:{" "}
        {formatDateTimeInline(budget.observedAt, dateFormat)}
      </p>
    </div>
  );
}
