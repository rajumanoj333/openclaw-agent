"use client";

import { ArrowRight, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { StepIndicator } from "@/components/step-indicator";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";

const CAP_LABELS: Record<string, string> = {
  social_media_posts: "Social media posts",
  marketing_campaigns: "Marketing campaigns",
  poster_design: "Poster / creative design",
  customer_replies: "Customer reply drafts",
  brand_strategy: "Brand strategy advice",
  competitor_research: "Competitor research",
  content_calendar: "Content calendar planning",
  analytics_summary: "Analytics summary",
};

export default function AgentDefinitionPage() {
  const router = useRouter();
  const [name, setName] = useState("Morpheus");
  const [caps, setCaps] = useState<string[]>([
    "social_media_posts",
    "marketing_campaigns",
    "poster_design",
  ]);
  const [extra, setExtra] = useState("");
  const [available, setAvailable] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api
      .capabilities()
      .then((r) => setAvailable(r.capabilities))
      .catch((e) => setErr(String(e)));
  }, []);

  const toggle = (c: string) =>
    setCaps((cur) =>
      cur.includes(c) ? cur.filter((x) => x !== c) : [...cur, c],
    );

  const submit = async () => {
    if (!name.trim() || caps.length === 0) return;
    setBusy(true);
    setErr(null);
    try {
      await api.saveAgent(name.trim(), caps, extra.trim());
      router.push("/chat");
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card p-8 fade-in">
      <StepIndicator active={2} />

      <h1 className="font-display italic text-[30px] leading-none tracking-editorial text-ink mb-3">
        Define your AI employee
      </h1>
      <p className="text-sm text-text-dim mb-6 leading-relaxed">
        Give your agent a name and check off the things it's allowed to handle.
        It will refuse anything outside this scope.
      </p>

      <label className="block mb-5">
        <span className="text-[11px] text-text-mute uppercase tracking-wider font-medium block mb-1.5">
          Agent name
        </span>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="w-full bg-bg border border-border rounded-xl px-3 py-2 text-sm text-text outline-none focus:border-text/40 transition"
        />
      </label>

      <div className="mb-5">
        <span className="text-[11px] text-text-mute uppercase tracking-wider font-medium block mb-2">
          Capabilities
        </span>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {available.map((c) => {
            const checked = caps.includes(c);
            return (
              <button
                key={c}
                type="button"
                onClick={() => toggle(c)}
                className={cn(
                  "text-left text-sm rounded-xl border px-3 py-2.5 flex items-center gap-2.5 transition",
                  checked
                    ? "bg-ink text-bg-elev border-ink shadow-ink"
                    : "bg-bg border-border text-text-dim hover:text-ink hover:border-border-strong",
                )}
              >
                <span
                  className={cn(
                    "w-4 h-4 rounded flex-shrink-0 flex items-center justify-center text-[10px] border",
                    checked
                      ? "bg-bg-elev border-bg-elev text-ink"
                      : "border-border-strong",
                  )}
                >
                  {checked ? "✓" : ""}
                </span>
                {CAP_LABELS[c] || c}
              </button>
            );
          })}
        </div>
      </div>

      <label className="block mb-7">
        <span className="text-[11px] text-text-mute uppercase tracking-wider font-medium block mb-1.5">
          Extra instructions (optional)
        </span>
        <textarea
          value={extra}
          onChange={(e) => setExtra(e.target.value)}
          rows={3}
          placeholder="e.g. always include #SupportLocal hashtag, avoid emojis in captions, etc."
          className="w-full bg-bg border border-border rounded-xl px-3 py-2 text-sm text-text outline-none focus:border-text/40 transition placeholder:text-text-mute"
        />
      </label>

      <div className="flex gap-2 justify-end pt-5 border-t border-border">
        <button
          onClick={() => router.push("/onboarding/confirm")}
          className="px-4 py-2 rounded-full border border-border text-text-dim hover:text-text hover:border-border-strong transition text-sm"
        >
          Back
        </button>
        <button
          onClick={submit}
          disabled={busy || !name.trim() || caps.length === 0}
          className="btn-primary flex items-center gap-2 disabled:opacity-50"
        >
          {busy ? (
            <Loader2 size={16} className="animate-spin" />
          ) : (
            <ArrowRight size={16} />
          )}
          Save and start chatting
        </button>
      </div>

      {err && (
        <p className="mt-3 text-xs text-danger bg-danger/10 border border-danger/20 rounded-xl p-3 break-all">
          {err}
        </p>
      )}
    </div>
  );
}
