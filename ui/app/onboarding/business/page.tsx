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
    <div className="bg-panel/70 backdrop-blur border border-border rounded-2xl p-8 fade-in shadow-2xl">
      <StepIndicator active={0} />

      <div className="flex items-center gap-3 mb-2">
        <div className="w-10 h-10 rounded-xl bg-accent/15 border border-accent/40 flex items-center justify-center">
          <Globe size={20} className="text-accent" />
        </div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Tell me about your business
        </h1>
      </div>
      <p className="text-sm text-text-dim mb-7 ml-13 pl-1">
        Paste your website, Instagram, or Google Maps link. I'll read it and
        pick out your services, brand colors, logo, and tone.
      </p>

      <label className="text-xs text-text-dim block mb-1.5 font-medium">
        Business link
      </label>
      <input
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        placeholder="https://your-business.com or instagram.com/yourhandle"
        className="w-full bg-bg border border-border rounded-xl px-3.5 py-2.5 mb-4 outline-none focus:border-accent transition text-sm"
        disabled={busy}
        autoFocus
      />

      <button
        onClick={submit}
        disabled={busy || !url.trim()}
        className="w-full bg-accent hover:bg-accent/90 text-bg rounded-xl py-2.5 font-medium disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 transition"
      >
        {busy ? (
          <>
            <Loader2 size={16} className="animate-spin" />
            Reading your site… this can take 60–120 sec
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
        <p className="mt-3 text-xs text-danger bg-danger/10 border border-danger/30 rounded-lg p-2.5 break-all">
          {err}
        </p>
      )}

      <div className="mt-6 pt-5 border-t border-border">
        <p className="text-xs text-text-mute leading-relaxed">
          <strong className="text-text-dim">Tip:</strong> websites with /about
          or /contact pages work best. Instagram & Facebook often block
          scrapers — try your website first.
        </p>
      </div>
    </div>
  );
}
