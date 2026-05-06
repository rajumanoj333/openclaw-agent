"use client";

import { ArrowRight, Globe, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { LiveStatus } from "@/components/live-status";
import { StepIndicator } from "@/components/step-indicator";
import { api } from "@/lib/api";

export default function BusinessUrlPage() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const submit = async () => {
    if (!url.trim()) return;
    setBusy(true);
    setErr(null);
    try {
      await api.scrape(url.trim());
      router.push("/onboarding/confirm");
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card p-8 fade-in">
      <StepIndicator active={0} />

      <div className="flex items-center gap-3 mb-3">
        <div className="w-11 h-11 rounded-2xl bg-bg border border-border flex items-center justify-center">
          <Globe size={18} className="text-text-dim" />
        </div>
        <h1 className="font-display italic text-[30px] leading-none tracking-editorial text-ink">
          Tell me about your business
        </h1>
      </div>
      <p className="text-[14px] text-text-dim mb-7 leading-relaxed">
        Paste your website, Instagram, or Google Maps link. I'll read it and
        pull out your services, brand colors, logo, and tone.
      </p>

      <input
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        placeholder="https://your-business.com"
        className="w-full bg-bg border border-border rounded-2xl px-4 py-3 mb-4 outline-none focus:border-text/40 transition text-sm"
        disabled={busy}
        autoFocus
      />

      <button
        onClick={submit}
        disabled={busy || !url.trim()}
        className="btn-primary w-full flex items-center justify-center gap-2"
      >
        {busy ? (
          <>
            <Loader2 size={16} className="animate-spin" />
            Reading your site…
          </>
        ) : (
          <>
            Continue
            <ArrowRight size={16} />
          </>
        )}
      </button>

      {busy && (
        <div className="mt-4 flex justify-center">
          <LiveStatus />
        </div>
      )}

      {err && (
        <p className="mt-3 text-xs text-danger bg-danger/10 border border-danger/20 rounded-xl p-3 break-all">
          {err}
        </p>
      )}

      <div className="mt-7 pt-5 border-t border-border">
        <p className="text-xs text-text-mute leading-relaxed">
          <strong className="text-text-dim">Tip:</strong> websites with /about
          or /contact pages work best. Instagram & Facebook often block
          scrapers — try your website first.
        </p>
      </div>
    </div>
  );
}
