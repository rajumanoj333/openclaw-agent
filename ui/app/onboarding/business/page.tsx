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
    <div className="card p-5 sm:p-8 fade-in">
      <StepIndicator active={0} />

      <div className="flex items-start sm:items-center gap-3 mb-3">
        <div className="w-11 h-11 rounded-2xl bg-bg border border-border flex items-center justify-center flex-shrink-0">
          <Globe size={18} className="text-text-dim" />
        </div>
        <h1 className="font-display italic text-[24px] sm:text-[30px] leading-none tracking-editorial text-ink">
          Tell me about your business
        </h1>
      </div>
      <p className="text-[14px] text-text-dim mb-5 leading-relaxed">
        Paste your website, Instagram, or Google Maps link. I'll read it and
        pull out your services, brand colors, logo, and tone.
      </p>

      {/* What gets scraped — quick explainer so users know what to expect */}
      <ul className="text-[12px] text-text-mute space-y-1.5 mb-7 px-4 py-3 bg-bg border border-border rounded-2xl">
        <li>· <b className="text-text-dim">Homepage</b> · /about · /contact</li>
        <li>· <b className="text-text-dim">JSON-LD schema</b> if present (best signal)</li>
        <li>· <b className="text-text-dim">og:* meta tags</b> for description + image</li>
        <li>· <b className="text-text-dim">CSS palette</b> for brand colors</li>
        <li>· <b className="text-text-dim">Logo</b> via favicon, apple-touch-icon, or schema.org</li>
      </ul>

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
        <div className="mt-3 text-xs text-danger bg-danger/10 border border-danger/20 rounded-xl p-3" role="alert">
          <p className="font-medium mb-1">Could not read that site</p>
          <p className="font-mono text-[11px] break-all opacity-80">{err}</p>
        </div>
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
