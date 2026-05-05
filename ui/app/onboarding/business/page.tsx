"use client";

import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
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
    <div className="bg-panel border border-border rounded-2xl p-8">
      <StepIndicator active={0} />

      <h1 className="text-2xl font-semibold mb-2">Tell me about your business</h1>
      <p className="text-sm text-white/60 mb-6">
        Paste your website, Instagram profile, or Google Maps link. I'll read
        the page, pick out your services, brand colors, logo, and tone — then
        ask you to confirm.
      </p>

      <label className="text-xs text-white/60 block mb-1">Business link</label>
      <input
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        placeholder="https://your-business.com or instagram.com/yourhandle"
        className="w-full bg-bg border border-border rounded-xl px-3 py-2 mb-3 outline-none focus:border-accent/60"
        disabled={busy}
        autoFocus
      />

      <button
        onClick={submit}
        disabled={busy || !url.trim()}
        className="w-full bg-accent text-bg rounded-xl py-2 font-medium disabled:opacity-50 flex items-center justify-center gap-2"
      >
        {busy ? <Loader2 size={16} className="animate-spin" /> : null}
        {busy ? "Reading your site… (~30 sec)" : "Continue"}
      </button>

      {err && (
        <p className="mt-3 text-xs text-red-300 bg-red-500/10 border border-red-500/30 rounded-lg p-2 break-all">
          {err}
        </p>
      )}

      <p className="mt-6 text-xs text-white/40">
        Tip: a website with an /about or /contact page works best. Instagram &
        Facebook often block scrapers — try your website first.
      </p>
    </div>
  );
}
