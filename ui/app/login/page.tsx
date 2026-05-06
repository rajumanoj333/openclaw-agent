"use client";

import { ArrowRight } from "lucide-react";
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
      <div className="text-center mb-10 rise">
        <p className="rule mb-5 max-w-[140px] mx-auto">
          <span>est. 2026</span>
        </p>
        <h1 className="font-display italic text-[64px] leading-none tracking-editorial text-ink">
          Morpheus
        </h1>
        <p className="mt-3 text-[14px] text-text-dim font-mono uppercase tracking-[0.2em]">
          your marketing employee
        </p>
      </div>

      <div className="card w-full max-w-sm p-8 fade-in">
        <div className="flex justify-center mb-7 relative">
          <div className="w-28 h-28 blob" />
          <span
            aria-hidden
            className="absolute inset-0 flex items-center justify-center font-display italic text-[44px] text-ink/85 tracking-editorial"
          >
            M
          </span>
        </div>

        <h2 className="font-display italic text-[26px] leading-none text-ink text-center tracking-editorial mb-2">
          Sign in
        </h2>
        <p className="text-[14px] text-text-dim text-center mb-7 leading-relaxed">
          One thread. WhatsApp, voice, and web — synced.
        </p>

        <input
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          onKeyDown={onKey}
          placeholder="+91 9999999999"
          autoFocus
          className="w-full bg-bg border border-border rounded-2xl px-4 py-3 mb-3 outline-none focus:border-ink/40 transition text-[15px] text-ink placeholder:text-text-mute font-mono"
          disabled={busy}
        />

        <button
          disabled={busy || !phone.trim() || phone.trim() === "+"}
          onClick={submit}
          className="btn-primary w-full inline-flex items-center justify-center gap-2"
        >
          {busy ? "Signing in…" : "Continue"}
          {!busy && <ArrowRight size={15} strokeWidth={2.4} />}
        </button>

        {err && (
          <p className="mt-3 text-[12px] text-danger bg-danger/10 border border-danger/20 rounded-xl p-3 break-all font-mono">
            {err}
          </p>
        )}
      </div>

      <p className="mt-7 font-mono text-[11px] text-text-mute text-center uppercase tracking-[0.18em]">
        Demo mode — any phone signs in instantly
      </p>
    </main>
  );
}
