"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
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
    <main className="min-h-screen flex flex-col items-center justify-center px-4">
      <h1 className="text-3xl font-medium tracking-tight text-text mb-12">
        Morpheus
      </h1>

      <div className="card w-full max-w-sm p-8 fade-in">
        <div className="flex justify-center mb-8">
          <div className="w-24 h-24 blob" />
        </div>

        <h2 className="text-base font-medium text-text text-center mb-2">
          Sign in
        </h2>
        <p className="text-sm text-text-dim text-center mb-7 leading-relaxed">
          Your AI marketing employee. WhatsApp, voice, and web — synced.
        </p>

        <input
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          onKeyDown={onKey}
          placeholder="+91 9999999999"
          autoFocus
          className="w-full bg-bg border border-border rounded-2xl px-4 py-3 mb-3 outline-none focus:border-text/40 transition text-sm"
          disabled={busy}
        />

        <button
          disabled={busy || !phone.trim() || phone.trim() === "+"}
          onClick={submit}
          className="btn-primary w-full"
        >
          {busy ? "Signing in…" : "Continue →"}
        </button>

        {err && (
          <p className="mt-3 text-xs text-danger bg-danger/10 border border-danger/20 rounded-xl p-3 break-all">
            {err}
          </p>
        )}
      </div>

      <p className="mt-6 text-[11px] text-text-mute text-center">
        Demo mode — any phone signs in instantly
      </p>
    </main>
  );
}
