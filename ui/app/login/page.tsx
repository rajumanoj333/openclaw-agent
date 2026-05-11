"use client";

import { ArrowRight, Globe, MessageCircle, Phone } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, saveAuth } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [phone, setPhone] = useState("+91");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [waNumber, setWaNumber] = useState<string | null>(null);
  const [voiceNumber, setVoiceNumber] = useState<string | null>(null);
  const [demoMode, setDemoMode] = useState(true);

  useEffect(() => {
    api
      .channels()
      .then((c) => {
        setWaNumber(c.whatsapp);
        setVoiceNumber(c.voice);
        setDemoMode(c.demo_mode);
      })
      .catch(() => {
        /* non-fatal — fallback to generic copy */
      });
  }, []);

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
    <main className="min-h-screen flex flex-col items-center justify-center px-4 py-10">
      <div className="text-center mb-8 rise">
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

      <div className="card w-full max-w-md p-8 fade-in">
        <div className="flex justify-center mb-6 relative">
          <div className="w-24 h-24 blob" />
          <span
            aria-hidden
            className="absolute inset-0 flex items-center justify-center font-display italic text-[40px] text-ink/85 tracking-editorial"
          >
            M
          </span>
        </div>

        <h2 className="font-display italic text-[26px] leading-none text-ink text-center tracking-editorial mb-2">
          Your phone is the routing key
        </h2>
        <p className="text-[13px] text-text-dim text-center mb-6 leading-relaxed">
          One number identifies your business across every channel. WhatsApp,
          voice call, and this web chat all hit the same agent.
        </p>

        {/* Routing explanation — three rows, each shows the inbound point */}
        <ul className="space-y-3 mb-7 text-[13px] text-text-dim">
          <li className="flex items-start gap-3">
            <span className="mt-0.5 w-8 h-8 rounded-full bg-whatsapp/10 flex items-center justify-center flex-shrink-0">
              <MessageCircle size={15} className="text-whatsapp" />
            </span>
            <div className="min-w-0">
              <p>
                <b className="text-ink">WhatsApp</b> — send messages or voice
                notes to{" "}
                <span className="font-mono text-ink text-[12px]">
                  {waNumber ?? "the Twilio number"}
                </span>
                . Agent replies on the same thread.
              </p>
            </div>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-0.5 w-8 h-8 rounded-full bg-voice/10 flex items-center justify-center flex-shrink-0">
              <Phone size={15} className="text-voice" />
            </span>
            <div className="min-w-0">
              <p>
                <b className="text-ink">Voice</b> — call{" "}
                <span className="font-mono text-ink text-[12px]">
                  {voiceNumber ?? "the Twilio voice line"}
                </span>{" "}
                · speak English or Telugu · hear the reply, also gets sent on
                WhatsApp.
              </p>
            </div>
          </li>
          <li className="flex items-start gap-3">
            <span className="mt-0.5 w-8 h-8 rounded-full bg-ui/10 flex items-center justify-center flex-shrink-0">
              <Globe size={15} className="text-ui" />
            </span>
            <div className="min-w-0">
              <p>
                <b className="text-ink">Web chat</b> — this screen. Every
                message from every channel lands here in real time. Send from
                here too.
              </p>
            </div>
          </li>
        </ul>

        <label
          htmlFor="phone-input"
          className="block font-mono text-[10px] uppercase tracking-[0.18em] text-text-mute mb-1.5"
        >
          Your phone number
        </label>
        <input
          id="phone-input"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          onKeyDown={onKey}
          placeholder="+91 9999999999"
          autoFocus
          className="w-full bg-bg border border-border rounded-2xl px-4 py-3 mb-2 outline-none focus:border-ink/40 transition text-[15px] text-ink placeholder:text-text-mute font-mono"
          disabled={busy}
        />
        <p className="text-[11px] text-text-mute mb-4 leading-relaxed">
          Use the same number you'll text or call from. The agent finds your
          business by this number on every channel.
        </p>

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

      <p className="mt-6 font-mono text-[11px] text-text-mute text-center uppercase tracking-[0.18em]">
        {demoMode
          ? "Demo mode — any phone signs in instantly. No OTP."
          : "Production — OTP verification required."}
      </p>
    </main>
  );
}
