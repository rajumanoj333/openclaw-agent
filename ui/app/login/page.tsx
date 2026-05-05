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
    <main className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-sm bg-panel border border-border rounded-2xl p-6">
        <h1 className="text-xl font-semibold mb-1">Sign in to Morpheus</h1>
        <p className="text-sm text-white/50 mb-6">
          Enter your phone number to continue. No password needed.
        </p>

        <label className="text-xs text-white/60 block mb-1">Phone (E.164)</label>
        <input
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          onKeyDown={onKey}
          placeholder="+919999999999"
          autoFocus
          className="w-full bg-bg border border-border rounded-xl px-3 py-2 mb-3 outline-none focus:border-accent/60"
          disabled={busy}
        />

        <button
          disabled={busy || !phone.trim() || phone.trim() === "+"}
          onClick={submit}
          className="w-full bg-accent text-bg rounded-xl py-2 font-medium disabled:opacity-50"
        >
          {busy ? "Signing in…" : "Continue →"}
        </button>

        {err && (
          <p className="mt-3 text-xs text-red-300 bg-red-500/10 border border-red-500/30 rounded-lg p-2 break-all">
            {err}
          </p>
        )}

        <p className="mt-6 text-[11px] text-white/40 leading-relaxed">
          Demo mode: any phone signs in instantly. Production will add OTP.
        </p>
      </div>
    </main>
  );
}
