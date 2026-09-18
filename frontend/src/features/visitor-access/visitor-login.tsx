import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuthStore } from "@/features/auth/hooks/use-auth";
import { relayRequest } from "./api";

export function VisitorLogin() {
  const { i18n } = useTranslation();
  const zh = i18n.language.startsWith("zh");
  const queryClient = useQueryClient();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return <form className="mt-4 space-y-3 rounded-xl border bg-card p-5" onSubmit={async (event) => {
    event.preventDefault(); setBusy(true); setError(null);
    try {
      await relayRequest("/api/visitor/login", { method: "POST", body: JSON.stringify({ username, password }) });
      queryClient.clear();
      await useAuthStore.getState().refreshSession();
      setPassword("");
    } catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
    finally { setBusy(false); }
  }}>
    <h2 className="font-semibold">{zh ? "访客登录" : "Visitor sign in"}</h2>
    <Input aria-label={zh ? "访客账号" : "Visitor username"} placeholder={zh ? "访客账号" : "Username"}
      autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} required />
    <Input aria-label={zh ? "访客密码" : "Visitor password"} placeholder={zh ? "访客密码" : "Password"}
      type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    <Button className="w-full" disabled={busy} type="submit">{zh ? "访客登录" : "Sign in as visitor"}</Button>
  </form>;
}
