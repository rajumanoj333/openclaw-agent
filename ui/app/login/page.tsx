"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, saveAuth } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [phone, setPhone] = useState("+91");
  const [code, setCode] = useState("");
  const [stage, setStage] = useState<"phone" | "code">("phone");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [hint, setHint] = useState<string | null>(null);

  const startOtp = async () => {
    setBusy(true);
    setErr(null);
    try {
      const r = await api.authStart(phone.trim());
      setStage("code");
      setHint(r.demo_hint || null);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  const verify = async () => {
    setBusy(true);
    setErr(null);
    try {
      const r = await api.authVerify(phone.trim(), code.trim());
      saveAuth(r.token, r.phone);
      router.push("/onboarding");
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-sm bg-panel border border-border rounded-2xl p-6">
        <h1 className="text-xl font-semibold mb-1">Sign in to Morpheus</h1>
        <p className="text-sm text-white/50 mb-6">
          Enter your WhatsApp number — we'll send a one-time code.
        </p>

        {stage === "phone" && (
          <>
            <label className="text-xs text-white/60 block mb-1">Phone (E.164)</label>
            <input
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="+919999999999"
              className="w-full bg-bg border border-border rounded-xl px-3 py-2 mb-3 outline-none focus:border-accent/60"
            />
            <button
              disabled={busy}
              onClick={startOtp}
              className="w-full bg-accent text-bg rounded-xl py-2 font-medium disabled:opacity-50"
            >
              {busy ? "Sending…" : "Send code"}
            </button>
          </>
        )}

        {stage === "code" && (
          <>
            <p className="text-xs text-white/60 mb-3">
              Code sent to <span className="text-white">{phone}</span>.
            </p>
            <label className="text-xs text-white/60 block mb-1">6-digit code</label>
            <input
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="123456"
              inputMode="numeric"
              className="w-full bg-bg border border-border rounded-xl px-3 py-2 mb-3 outline-none focus:border-accent/60 tracking-widest text-center"
            />
            <button
              disabled={busy}
              onClick={verify}
              className="w-full bg-accent text-bg rounded-xl py-2 font-medium disabled:opacity-50"
            >
              {busy ? "Verifying…" : "Sign in"}
            </button>
            <button
              onClick={() => setStage("phone")}
              className="w-full mt-2 text-xs text-white/50 hover:text-white"
            >
              Back
            </button>
          </>
        )}

        {hint && (
          <p className="mt-4 text-xs text-warn bg-warn/10 border border-warn/30 rounded-lg p-2">
            Demo hint: {hint}
          </p>
        )}
        {err && (
          <p className="mt-3 text-xs text-red-300 bg-red-500/10 border border-red-500/30 rounded-lg p-2 break-all">
            {err}
          </p>
        )}
      </div>
    </main>
  );
}
