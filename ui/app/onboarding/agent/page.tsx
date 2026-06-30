"use client";

import {
  ArrowRight,
  Check,
  Image as ImageIcon,
  Loader2,
  Receipt,
  Share2,
  TrendingUp,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { StepIndicator } from "@/components/step-indicator";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";

interface AgentCard {
  slug: string;
  name: string;
  role: string;
  icon: string;
  color: string;
  scope: string[];
}

const ICONS: Record<string, React.ReactNode> = {
  image: <ImageIcon size={20} />,
  "share-2": <Share2 size={20} />,
  receipt: <Receipt size={20} />,
  "trending-up": <TrendingUp size={20} />,
};

// Map backend color tokens → Tailwind class fragments (static so JIT picks them up)
const COLOR_CLASSES: Record<
  string,
  { bg: string; text: string; border: string; ring: string }
> = {
  ui:       { bg: "bg-ui/10",       text: "text-ui",       border: "border-ui/40",       ring: "ring-ui/30" },
  whatsapp: { bg: "bg-whatsapp/10", text: "text-whatsapp", border: "border-whatsapp/40", ring: "ring-whatsapp/30" },
  voice:    { bg: "bg-voice/10",    text: "text-voice",    border: "border-voice/40",    ring: "ring-voice/30" },
  warn:     { bg: "bg-warn/10",     text: "text-warn",     border: "border-warn/40",     ring: "ring-warn/30" },
};


export default function AgentDefinitionPage() {
  const router = useRouter();
  const [name, setName] = useState("Morpheus");
  const [enabled, setEnabled] = useState<string[]>(["morpheus", "ritu"]);
  const [extra, setExtra] = useState("");
  const [agents, setAgents] = useState<AgentCard[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api
      .availableAgents()
      .then((r) => {
        setAgents(r.agents);
        // Default = all enabled if none picked yet
        if (r.agents.length && enabled.length === 0) {
          setEnabled(r.agents.map((a) => a.slug));
        }
      })
      .catch((e) => setErr(String(e)));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggle = (slug: string) =>
    setEnabled((cur) =>
      cur.includes(slug) ? cur.filter((x) => x !== slug) : [...cur, slug],
    );

  const submit = async () => {
    if (!name.trim() || enabled.length === 0) return;
    setBusy(true);
    setErr(null);
    try {
      await api.saveAgent(name.trim(), enabled, extra.trim());
      router.push("/chat");
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card p-6 sm:p-10 fade-in">
      <StepIndicator active={2} />

      <div className="mb-7">
        <h1 className="font-display italic text-[28px] sm:text-[36px] leading-[1.05] tracking-editorial text-ink mb-2">
          Build your team
        </h1>
        <p className="text-[14px] text-text-dim leading-relaxed">
          Pick the agents you want for your business. Each one is strictly
          scoped — Ritu only does social media, Kiran only invoices, etc.
          Out-of-scope requests get politely redirected to the right teammate.
        </p>
      </div>

      {/* ─── Team name ──────────────────────────────────────── */}
      <div className="mb-7">
        <label className="block">
          <span className="font-mono text-[10px] text-text-mute uppercase tracking-[0.18em] block mb-1.5">
            Team name
          </span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Morpheus"
            className="w-full bg-bg border border-border rounded-xl px-3.5 py-2.5 text-[14px] text-ink outline-none focus:border-ink/40 transition"
          />
          <p className="text-[11px] text-text-mute mt-1.5">
            The umbrella name for your AI marketing studio — shown in the chat
            header.
          </p>
        </label>
      </div>

      {/* ─── Agent cards ──────────────────────────────────────── */}
      <div className="mb-7">
        <div className="flex items-baseline justify-between mb-3">
          <h2 className="font-display italic text-[20px] text-ink tracking-editorial leading-none">
            Your team
          </h2>
          <span className="font-mono text-[11px] text-text-mute uppercase tracking-wider">
            {enabled.length} of {agents.length} enabled
          </span>
        </div>

        {agents.length === 0 ? (
          <div className="text-center py-8 text-text-mute text-[13px]">
            <Loader2 size={16} className="animate-spin inline-block mr-2" />
            Loading agents…
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {agents.map((a) => (
              <AgentCardButton
                key={a.slug}
                agent={a}
                active={enabled.includes(a.slug)}
                onToggle={() => toggle(a.slug)}
              />
            ))}
          </div>
        )}

        {enabled.length === 0 && (
          <p className="mt-3 text-[12px] text-danger">
            Pick at least one agent.
          </p>
        )}
      </div>

      {/* ─── Extra instructions ───────────────────────────────── */}
      <div className="mb-7">
        <label className="block">
          <span className="font-mono text-[10px] text-text-mute uppercase tracking-[0.18em] block mb-1.5">
            Extra instructions (optional)
          </span>
          <textarea
            value={extra}
            onChange={(e) => setExtra(e.target.value)}
            rows={3}
            placeholder="e.g. always include #SupportLocal hashtag, avoid emojis in captions, mention free delivery for orders above ₹500…"
            className="w-full bg-bg border border-border rounded-xl px-3.5 py-2.5 text-[14px] text-ink outline-none focus:border-ink/40 transition placeholder:text-text-mute"
          />
          <p className="text-[11px] text-text-mute mt-1.5">
            Owner-only rules every agent must follow.
          </p>
        </label>
      </div>

      {/* ─── Actions ──────────────────────────────────────────── */}
      <div className="pt-6 border-t border-border flex flex-col-reverse sm:flex-row gap-3 sm:justify-end sm:items-center">
        <button
          onClick={() => router.push("/onboarding/confirm")}
          className="px-5 py-2.5 rounded-full border border-border text-text-dim hover:text-ink hover:border-border-strong transition text-[13px]"
        >
          Back
        </button>
        <button
          onClick={submit}
          disabled={busy || !name.trim() || enabled.length === 0}
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
        <div
          className="mt-4 text-[12px] text-danger bg-danger/10 border border-danger/20 rounded-xl p-3"
          role="alert"
        >
          <p className="font-medium mb-1">Could not save your team</p>
          <p className="font-mono text-[11px] break-all opacity-80">{err}</p>
        </div>
      )}
    </div>
  );
}


function AgentCardButton({
  agent,
  active,
  onToggle,
}: {
  agent: AgentCard;
  active: boolean;
  onToggle: () => void;
}) {
  const colors = COLOR_CLASSES[agent.color] ?? COLOR_CLASSES.ui;
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-pressed={active}
      className={cn(
        "text-left rounded-2xl p-4 border-2 transition flex items-start gap-3 relative",
        active
          ? cn(colors.bg, colors.border, "shadow-soft")
          : "bg-bg border-border hover:border-border-strong",
      )}
    >
      <span
        className={cn(
          "w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0 transition",
          active ? "bg-bg-elev" : colors.bg,
        )}
      >
        <span className={colors.text}>{ICONS[agent.icon] ?? ICONS.image}</span>
      </span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <h3
            className={cn(
              "font-display italic text-[18px] tracking-editorial leading-none",
              active ? "text-ink" : "text-text-dim",
            )}
          >
            {agent.name}
          </h3>
          {active && (
            <span
              className={cn(
                "w-4 h-4 rounded-full flex items-center justify-center flex-shrink-0",
                "bg-ink text-bg-elev",
              )}
              aria-hidden
            >
              <Check size={10} strokeWidth={3} />
            </span>
          )}
        </div>
        <p
          className={cn(
            "text-[11px] font-mono uppercase tracking-[0.15em] mb-2",
            active ? colors.text : "text-text-mute",
          )}
        >
          {agent.role}
        </p>
        <ul className="space-y-0.5">
          {agent.scope.slice(0, 4).map((s) => (
            <li
              key={s}
              className={cn(
                "text-[12px] leading-snug",
                active ? "text-text-dim" : "text-text-mute",
              )}
            >
              · {s}
            </li>
          ))}
        </ul>
      </div>
    </button>
  );
}
