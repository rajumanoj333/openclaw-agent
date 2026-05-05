"use client";

import { Loader2 } from "lucide-react";
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
    <div className="bg-panel border border-border rounded-2xl p-8">
      <StepIndicator active={2} />
      <h1 className="text-2xl font-semibold mb-1">Define your AI employee</h1>
      <p className="text-sm text-white/60 mb-6">
        Give your agent a name and check off the things it's allowed to handle.
        It will refuse anything outside this scope.
      </p>

      <label className="block mb-5">
        <span className="text-xs text-white/60 block mb-1">Agent name</span>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="w-full bg-bg border border-border rounded-xl px-3 py-2 outline-none focus:border-accent/60"
        />
      </label>

      <div className="mb-5">
        <span className="text-xs text-white/60 block mb-2">Capabilities</span>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {available.map((c) => {
            const checked = caps.includes(c);
            return (
              <button
                key={c}
                type="button"
                onClick={() => toggle(c)}
                className={cn(
                  "text-left text-sm rounded-lg border px-3 py-2 flex items-center gap-2",
                  checked
                    ? "bg-accent/15 border-accent/60 text-white"
                    : "bg-bg border-border text-white/60 hover:text-white hover:border-border/80",
                )}
              >
                <span
                  className={cn(
                    "w-4 h-4 rounded border flex-shrink-0 flex items-center justify-center text-[10px]",
                    checked
                      ? "bg-accent border-accent text-bg"
                      : "border-border",
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

      <label className="block mb-6">
        <span className="text-xs text-white/60 block mb-1">
          Extra instructions (optional)
        </span>
        <textarea
          value={extra}
          onChange={(e) => setExtra(e.target.value)}
          rows={3}
          placeholder="e.g. always include #SupportLocal hashtag, avoid emojis in captions, etc."
          className="w-full bg-bg border border-border rounded-xl px-3 py-2 text-sm outline-none focus:border-accent/60"
        />
      </label>

      <div className="flex gap-2 justify-end">
        <button
          onClick={() => router.push("/onboarding/confirm")}
          className="px-4 py-2 rounded-xl border border-border text-white/70 hover:text-white"
        >
          Back
        </button>
        <button
          onClick={submit}
          disabled={busy || !name.trim() || caps.length === 0}
          className="px-5 py-2 rounded-xl bg-accent text-bg font-medium disabled:opacity-50 flex items-center gap-2"
        >
          {busy ? <Loader2 size={16} className="animate-spin" /> : null}
          Save and start chatting
        </button>
      </div>

      {err && (
        <p className="mt-3 text-xs text-red-300 bg-red-500/10 border border-red-500/30 rounded-lg p-2 break-all">
          {err}
        </p>
      )}
    </div>
  );
}
