"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Sparkles } from "lucide-react";
import { api, saveAuth } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [phone, setPhone] = useState("+91");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async () => {
    if (!phone.trim() || phone.trim() === "+") return;
    setBusy(true);
    setErr(null);
    try {
      const r = await api.login(phone.trim());
      saveAuth(r.token, r.phone);
      router.push("/onboarding");
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  const onKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") submit();
  };

  return (
    <main className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-sm fade-in">
        <div className="flex items-center justify-center mb-8">
          <div className="w-12 h-12 rounded-2xl bg-accent/20 border border-accent/40 flex items-center justify-center">
            <Sparkles className="text-accent" size={22} />
          </div>
        </div>

        <div className="bg-panel/70 backdrop-blur border border-border rounded-2xl p-7 shadow-2xl">
          <h1 className="text-2xl font-semibold tracking-tight mb-1.5">
            Sign in to Morpheus
          </h1>
          <p className="text-sm text-text-dim mb-6">
            Your AI marketing employee. WhatsApp, voice, and web — all in sync.
          </p>

          <label className="text-xs text-text-dim block mb-1.5 font-medium">
            Phone number
          </label>
          <input
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            onKeyDown={onKey}
            placeholder="+919999999999"
            autoFocus
            className="w-full bg-bg border border-border rounded-xl px-3.5 py-2.5 mb-4 outline-none focus:border-accent transition text-sm"
            disabled={busy}
          />

          <button
            disabled={busy || !phone.trim() || phone.trim() === "+"}
            onClick={submit}
            className="w-full bg-accent hover:bg-accent/90 text-bg rounded-xl py-2.5 font-medium disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            {busy ? "Signing in…" : "Continue →"}
          </button>

          {err && (
            <p className="mt-3 text-xs text-danger bg-danger/10 border border-danger/30 rounded-lg p-2.5 break-all">
              {err}
            </p>
          )}
        </div>

        <p className="mt-6 text-[11px] text-text-mute text-center">
          Demo mode: any phone signs in instantly.
        </p>
      </div>
    </main>
  );
}
