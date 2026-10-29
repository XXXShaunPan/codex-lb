import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { relayRequest } from "@/features/visitor-access/api";

type ImageSettingsData = {
  hostModel: string | null;
  resolvedHostModel: string | null;
  availableHostModels: string[];
};

export function ImageRoutingSettings() {
  const { i18n } = useTranslation();
  const zh = i18n.language.startsWith("zh");
  const client = useQueryClient();
  const settings = useQuery({
    queryKey: ["image-routing-settings"],
    queryFn: () =>
      relayRequest<ImageSettingsData>("/api/image-routing/settings"),
  });
  const [draft, setDraft] = useState<string | null>(null);
  const update = useMutation({
    mutationFn: (hostModel: string | null) =>
      relayRequest<ImageSettingsData>("/api/image-routing/settings", {
        method: "PUT",
        body: JSON.stringify({ hostModel }),
      }),
    onSuccess: async () => {
      setDraft(null);
      await client.invalidateQueries({ queryKey: ["image-routing-settings"] });
    },
  });
  return (
    <section className="space-y-3 rounded-xl border bg-card p-5">
      <h3 className="font-semibold">
        {zh ? "图片模型路由" : "Image model routing"}
      </h3>
      <p className="text-sm text-muted-foreground">
        {zh
          ? "图片模型保持为请求中的 gpt-image-*。实体账号使用下方宿主调用图片工具；Model Source 使用原始图片接口，并参加同一套共享路由策略。自定义加权策略按权重 × 最低剩余比例随机分配，不区分套餐或账号优先级。"
          : "The requested gpt-image model remains unchanged. Subscription accounts use a separate tool host; model sources use their Images API and share the same routing strategy. Custom weighted routing draws by weight × minimum remaining quota, without plan or account priority groups."}
      </p>
      <label className="block text-sm">
        {zh
          ? "实体账号的图片工具宿主（留空自动选择）"
          : "Subscription image-tool host (blank selects automatically)"}
        <Input
          list="image-host-models"
          value={draft ?? settings.data?.hostModel ?? ""}
          onChange={(e) => setDraft(e.target.value)}
          placeholder={zh ? "自动选择" : "Automatic"}
        />
      </label>
      <datalist id="image-host-models">
        {settings.data?.availableHostModels.map((model) => (
          <option key={model} value={model} />
        ))}
      </datalist>
      <p className="text-xs text-muted-foreground">
        {zh ? "当前宿主：" : "Current host: "}
        {settings.data?.resolvedHostModel ?? "—"}
      </p>
      {(settings.error || update.error) && (
        <p role="alert" className="text-destructive">
          {settings.error?.message ?? update.error?.message}
        </p>
      )}
      <Button
        disabled={draft === null || update.isPending}
        onClick={() => update.mutate(draft?.trim() || null)}
      >
        {zh ? "保存" : "Save"}
      </Button>
    </section>
  );
}
