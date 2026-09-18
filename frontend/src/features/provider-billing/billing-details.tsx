import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { relayRequest } from "@/features/visitor-access/api";

type BillingEntry = {
  id:string; pricing_version:string; pricing_source:string; service_tier:string;
  uncached_input_tokens:number; cached_read_tokens:number; cache_write_tokens:number|null;
  output_tokens:number; cost_usd:number; charged_usd:number; provider_cost_usd:number|null;
  tool_call_cost:number|null; usage_basis:string;
};

export function BillingDetails({requestId}:{requestId:string}) {
  const {i18n} = useTranslation();
  const zh = i18n.language.startsWith("zh");
  const {data,error} = useQuery({queryKey:["provider-billing",requestId],queryFn:()=>relayRequest<{entries:BillingEntry[]}>(`/api/provider-billing/${encodeURIComponent(requestId)}`)});
  if(error) return <p role="alert" className="text-xs text-destructive">{error.message}</p>;
  if(!data?.entries.length) return null;
  const unknown = zh ? "未提供" : "Not reported";
  return <section className="space-y-3 rounded border p-3 text-xs"><h3 className="font-semibold">{zh ? "计费明细与价格快照" : "Billing details and price snapshot"}</h3>
    {data.entries.map(row=><div key={row.id} className="space-y-2">
      <dl className="grid grid-cols-2 gap-2">
        <dt>{zh ? "非缓存输入 / 缓存读取" : "Uncached input / cache read"}</dt><dd>{row.uncached_input_tokens} / {row.cached_read_tokens}</dd>
        <dt>{zh ? "缓存写入 / 输出" : "Cache write / output"}</dt><dd>{row.cache_write_tokens ?? unknown} / {row.output_tokens}</dd>
        <dt>{zh ? "等级 / 用量依据" : "Tier / usage basis"}</dt><dd>{row.service_tier} / {row.usage_basis}</dd>
        <dt>{zh ? "用户费用" : "Customer charge"}</dt><dd>${row.charged_usd.toFixed(6)}</dd>
        <dt>{zh ? "上游成本 / 工具费" : "Provider cost / tool cost"}</dt><dd>{row.provider_cost_usd ?? unknown} / {row.tool_call_cost ?? unknown}</dd>
      </dl><p className="break-all text-muted-foreground">{row.pricing_source} · {row.pricing_version}</p>
    </div>)}
  </section>;
}
