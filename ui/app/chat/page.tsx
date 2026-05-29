"use client";

import {
  Activity,
  Globe,
  Image as ImageIcon,
  LogOut,
  Menu,
  MessageCircle,
  Phone,
  Receipt,
  RotateCcw,
  Share2,
  TrendingUp,
  X,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { Composer } from "@/components/composer";
import { ConnectionPill } from "@/components/connection-pill";
import { MessageBubble } from "@/components/message-bubble";
import { SystemStatus } from "@/components/system-status";
import { cn } from "@/lib/cn";
import {
  api,
  clearAuth,
  getPhone,
  getToken,
  type AgentCfg,
  type BusinessProfileT,
} from "@/lib/api";
import { openChatSocket, type ChatEvent, type ChatSocket } from "@/lib/ws";


// Static agent registry — must match backend (app/services/agents/*).
// Display-only metadata; intent/scope rules live server-side.
interface AgentCard {
  slug: string;
  name: string;
  role: string;
  scope: string;
  color: "ui" | "whatsapp" | "voice" | "warn";
  icon: React.ReactNode;
  composerPlaceholder: string;
  emptyHook: string;
  examples: string[];
}

const AGENTS: AgentCard[] = [
  {
    slug: "morpheus",
    name: "Morpheus",
    role: "Marketing & Poster",
    scope: "Campaigns, posters, brand visuals",
    color: "ui",
    icon: <ImageIcon size={15} />,
    composerPlaceholder: "Ask Morpheus to design a poster, campaign, or visual…",
    emptyHook: "Posters, campaigns, brand visuals. That's my lane.",
    examples: [
      "make me a diwali poster",
      "design a campaign for new admission",
      "create a flyer for monsoon sale",
    ],
  },
  {
    slug: "ritu",
    name: "Ritu",
    role: "Social Media Manager",
    scope: "Captions, posts, hashtags, replies",
    color: "whatsapp",
    icon: <Share2 size={15} />,
    composerPlaceholder: "Ask Ritu for a caption, post, or social reply…",
    emptyHook: "Captions, hashtags, posts. Bound to social only.",
    examples: [
      "write me an instagram caption for diwali",
      "draft a reply to this customer comment",
      "give me a content idea for tuesday",
    ],
  },
  {
    slug: "kiran",
    name: "Kiran",
    role: "Invoice & Payments",
    scope: "Invoices, payment reminders, GST",
    color: "voice",
    icon: <Receipt size={15} />,
    composerPlaceholder: "Ask Kiran for an invoice or payment reminder…",
    emptyHook: "Invoices, billing, reminders. Strictly numbers.",
    examples: [
      "draft an invoice for ₹5000 for laptop repair",
      "send a payment reminder for invoice INV-2026-001",
      "what's our GST tax line for software services?",
    ],
  },
  {
    slug: "anika",
    name: "Anika",
    role: "Business Advisor",
    scope: "Strategy, competition, pricing",
    color: "warn",
    icon: <TrendingUp size={15} />,
    composerPlaceholder: "Ask Anika for advice, strategy, or competitive insight…",
    emptyHook: "Strategy, pricing, competition. Decision-grade advice only.",
    examples: [
      "should i raise my prices?",
      "compare us against the nearby competitor",
      "which channel should i double down on this quarter?",
    ],
  },
];


export default function ChatPage() {
  const router = useRouter();
  const [events, setEvents] = useState<ChatEvent[]>([]);
  const [state, setState] = useState<"connecting" | "open" | "closed" | "error">(
    "connecting",
  );
  const [agent, setAgent] = useState<AgentCfg | null>(null);
  const [profile, setProfile] = useState<BusinessProfileT | null>(null);
  const [profileLoaded, setProfileLoaded] = useState(false);
  const [activeStatus, setActiveStatus] = useState<{
    status: string;
    body?: string;
  } | null>(null);
  const [pending, setPending] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [channels, setChannels] = useState<{
    whatsapp: string | null;
    voice: string | null;
  } | null>(null);
  const [activeAgent, setActiveAgent] = useState<string>("morpheus");
  const sockRef = useRef<ChatSocket | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const pendingTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    api
      .channels()
      .then((c) => setChannels({ whatsapp: c.whatsapp, voice: c.voice }))
      .catch(() => {});
  }, []);

  const phone = useMemo(() => getPhone(), []);
  const token = useMemo(() => getToken(), []);

  useEffect(() => {
    if (!phone || !token) {
      router.replace("/login");
      return;
    }

    api
      .onboardingStatus()
      .then((s) => {
        if (s.step !== "ready") {
          router.replace("/onboarding");
          return;
        }
        api.getAgent().then((cfg) => {
          setAgent(cfg);
          // Default active agent = first enabled one
          if (cfg?.enabled_agents && cfg.enabled_agents.length > 0) {
            setActiveAgent(cfg.enabled_agents[0]);
          }
        }).catch(() => {});
        api
          .getProfile()
          .then(setProfile)
          .catch(() => {})
          .finally(() => setProfileLoaded(true));
        const sock = openChatSocket(
          phone,
          (ev) => {
            if (ev.kind === "status") {
              setActiveStatus({
                status: ev.status || "working",
                body: ev.body || undefined,
              });
              if (
                ev.status?.endsWith("_done") ||
                ev.status === "agent_ready" ||
                ev.status === "profile_confirmed"
              ) {
                setTimeout(() => setActiveStatus(null), 6000);
              }
            } else {
              setEvents((cur) => [...cur, ev]);
              if (ev.direction === "out") {
                setPending(false);
                if (pendingTimerRef.current) {
                  clearTimeout(pendingTimerRef.current);
                  pendingTimerRef.current = null;
                }
              }
            }
          },
          setState,
        );
        sockRef.current = sock;
      })
      .catch(() => router.replace("/login"));

    return () => sockRef.current?.close();
  }, [phone, token, router]);

  // Events filtered to the active agent's thread. Includes:
  //   - all events with matching agent_slug
  //   - legacy events (no agent_slug) only when viewing the default agent
  const visibleEvents = useMemo(() => {
    return events.filter((ev) => {
      if (ev.agent_slug) return ev.agent_slug === activeAgent;
      // No agent_slug → legacy / WhatsApp inbound. Show only on the
      // first-enabled (default) agent so they don't double up.
      return activeAgent === (agent?.enabled_agents?.[0] ?? "morpheus");
    });
  }, [events, activeAgent, agent?.enabled_agents]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [visibleEvents.length, pending]);

  if (!phone) return null;

  const enabledSlugs = agent?.enabled_agents ?? ["morpheus", "ritu", "kiran", "anika"];
  const enabledAgents = AGENTS.filter((a) => enabledSlugs.includes(a.slug));
  const active = AGENTS.find((a) => a.slug === activeAgent) ?? AGENTS[0];

  // Unread counts per agent (messages from agent OR sent to that thread)
  const perAgentCounts = events.reduce<Record<string, number>>((acc, ev) => {
    if (!ev.agent_slug || ev.kind !== "message") return acc;
    acc[ev.agent_slug] = (acc[ev.agent_slug] ?? 0) + 1;
    return acc;
  }, {});

  const onSend = (body: string) => {
    setEvents((cur) => [
      ...cur,
      {
        phone: phone!,
        channel: "ui",
        direction: "in",
        body,
        kind: "message",
        agent_slug: activeAgent,
        ts: Date.now() / 1000,
      } as ChatEvent,
    ]);
    sockRef.current?.send(body, activeAgent);
    setPending(true);
    if (pendingTimerRef.current) clearTimeout(pendingTimerRef.current);
    pendingTimerRef.current = setTimeout(() => setPending(false), 5 * 60_000);
  };

  const logout = () => {
    sockRef.current?.close();
    clearAuth();
    router.replace("/login");
  };

  const reset = async () => {
    if (
      !confirm(
        "Reset clears your business profile + agent setup. You'll be sent back to onboarding. Continue?",
      )
    )
      return;
    try {
      await api.reset();
    } catch {
      /* ignore */
    }
    sockRef.current?.close();
    router.replace("/onboarding");
  };

  const counts = events.reduce(
    (acc, ev) => {
      const k = ev.channel === "system" ? "ui" : ev.channel;
      acc[k] = (acc[k] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>,
  );

  const businessName = profile?.name;

  return (
    <main className="h-screen flex">
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-ink/30 z-40 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* SIDEBAR */}
      <aside
        className={`w-80 flex flex-col border-r border-border bg-bg-elev/60 backdrop-blur-xl fixed inset-y-0 left-0 z-50 transition-transform duration-200 ease-out md:relative md:translate-x-0 overflow-y-auto ${sidebarOpen ? "translate-x-0" : "-translate-x-full"}`}
      >
        <button
          onClick={() => setSidebarOpen(false)}
          className="md:hidden absolute top-4 right-4 p-2 rounded-full hover:bg-bg transition"
          aria-label="Close sidebar"
        >
          <X size={18} className="text-text-mute" />
        </button>

        {/* Business header */}
        <div className="p-6 pb-5 border-b border-border">
          <div className="rule mb-4">
            <span>The Studio</span>
          </div>
          <h2 className="font-display text-[26px] leading-[1.05] text-ink italic font-medium tracking-editorial">
            {businessName || "Your Business"}
          </h2>
          <p className="mt-1 text-[11px] text-text-mute font-mono uppercase tracking-[0.18em]">
            {profile?.brand?.tone || "marketing studio"}
          </p>
          {profile?.brand && (
            <div className="flex gap-1.5 mt-3">
              {[
                profile.brand.primary_color,
                profile.brand.secondary_color,
                profile.brand.accent_color,
              ]
                .filter(Boolean)
                .map((c) => (
                  <span
                    key={c}
                    className="w-5 h-5 rounded-md border border-border shadow-soft"
                    style={{ backgroundColor: c! }}
                    title={c!}
                  />
                ))}
            </div>
          )}

          {!profile && profileLoaded && (
            <div className="mt-4 text-[12px] leading-relaxed bg-warn/8 border border-warn/20 rounded-xl p-3">
              <p className="text-warn font-medium mb-1.5">No profile linked</p>
              <button
                onClick={() => router.replace("/onboarding")}
                className="btn-primary text-[11px] px-3 py-1.5 inline-flex items-center gap-1.5"
              >
                Re-link business
              </button>
            </div>
          )}
        </div>

        {/* Agent picker */}
        <div className="p-6 border-b border-border">
          <h3 className="font-mono text-[10px] uppercase tracking-[0.2em] text-text-mute mb-3">
            Your team
          </h3>
          <div className="space-y-2">
            {enabledAgents.map((a) => (
              <AgentRow
                key={a.slug}
                agent={a}
                active={a.slug === activeAgent}
                unread={perAgentCounts[a.slug] ?? 0}
                onClick={() => {
                  setActiveAgent(a.slug);
                  setSidebarOpen(false);
                }}
              />
            ))}
          </div>
        </div>

        {/* Channels */}
        <div className="p-6 border-b border-border">
          <h3 className="font-mono text-[10px] uppercase tracking-[0.2em] text-text-mute mb-3">
            Channels
          </h3>
          <ChannelRow
            icon={<MessageCircle size={14} />}
            label="WhatsApp"
            count={counts.whatsapp || 0}
            color="whatsapp"
            target={channels?.whatsapp}
          />
          <ChannelRow
            icon={<Phone size={14} />}
            label="Voice"
            count={counts.voice || 0}
            color="voice"
            target={channels?.voice}
          />
          <ChannelRow
            icon={<Globe size={14} />}
            label="Web"
            count={counts.ui || 0}
            color="ui"
            target="this chat"
          />
        </div>

        <SystemStatus phone={phone} />

        <div className="mt-auto p-6 space-y-2">
          <button
            onClick={reset}
            className="btn-ghost w-full justify-center inline-flex items-center gap-2"
            title="Wipe profile + agent and redo onboarding"
          >
            <RotateCcw size={12} />
            Reset business
          </button>
          <button
            onClick={logout}
            className="btn-ghost w-full justify-center inline-flex items-center gap-2"
          >
            <LogOut size={12} />
            Sign out
          </button>
          <p className="font-mono text-[10px] text-text-mute text-center mt-3 tracking-wider">
            {phone}
          </p>
        </div>
      </aside>

      {/* MAIN */}
      <section className="flex-1 flex flex-col min-w-0">
        <header className="flex items-center justify-between px-4 md:px-8 py-4 md:py-5 border-b border-border bg-bg-elev/40 backdrop-blur-xl">
          <div className="flex items-center gap-3 min-w-0">
            <button
              onClick={() => setSidebarOpen(true)}
              className="md:hidden p-2 -ml-1 rounded-full hover:bg-bg transition"
              aria-label="Open sidebar"
            >
              <Menu size={20} className="text-text-dim" />
            </button>
            <span
              className={cn(
                "hidden md:inline-flex items-center justify-center w-9 h-9 rounded-full flex-shrink-0",
                agentColorBg(active.color),
              )}
            >
              <span className={agentColorText(active.color)}>{active.icon}</span>
            </span>
            <div className="min-w-0">
              <h1 className="font-display text-[20px] md:text-[24px] italic leading-none text-ink tracking-editorial truncate">
                {active.name}
              </h1>
              <p className="mt-1 text-[11px] md:text-[12px] text-text-mute font-mono truncate">
                {active.role} · acting for {businessName?.toLowerCase() || phone}
              </p>
            </div>
          </div>
          <ConnectionPill state={state} />
        </header>

        {activeStatus && (
          <div className="px-4 md:px-8 py-3 border-b border-border bg-warn/5">
            <div className="inline-flex items-center gap-2.5 text-[13px] text-warn">
              <Activity size={13} className="pulse-dot" />
              <span className="capitalize font-medium">
                {activeStatus.status.replace(/_/g, " ")}
              </span>
              {activeStatus.body && (
                <span className="text-text-mute truncate max-w-md">
                  — {activeStatus.body}
                </span>
              )}
            </div>
          </div>
        )}

        <section
          className="flex-1 overflow-y-auto px-4 md:px-8 py-6 md:py-8"
          role="log"
          aria-live="polite"
          aria-label={`Chat with ${active.name}`}
        >
          {visibleEvents.length === 0 && !activeStatus && (
            <div className="h-full flex items-center justify-center text-center">
              <div className="max-w-xl">
                <div
                  className={cn(
                    "w-16 h-16 mx-auto mb-5 rounded-full flex items-center justify-center",
                    agentColorBg(active.color),
                  )}
                  style={{ animationDelay: "60ms" }}
                >
                  <span className={cn("scale-150", agentColorText(active.color))}>
                    {active.icon}
                  </span>
                </div>
                <h2
                  className="font-display italic text-[28px] md:text-[36px] leading-[1.05] text-ink tracking-editorial mb-2 rise"
                  style={{ animationDelay: "180ms" }}
                >
                  Hi — I'm {active.name}.
                </h2>
                <p
                  className="text-[14px] text-text-mute font-mono uppercase tracking-[0.18em] mb-4 rise"
                  style={{ animationDelay: "250ms" }}
                >
                  {active.role}
                </p>
                <p
                  className="text-[14px] md:text-[15px] text-text-dim leading-relaxed mb-7 max-w-md mx-auto rise"
                  style={{ animationDelay: "320ms" }}
                >
                  {active.emptyHook}
                </p>
                <div
                  className="grid gap-2 text-left rise"
                  style={{ animationDelay: "420ms" }}
                >
                  {active.examples.map((ex) => (
                    <Suggestion key={ex} text={ex} onSend={onSend} />
                  ))}
                </div>
              </div>
            </div>
          )}
          {visibleEvents.map((ev, i) => (
            <MessageBubble key={`${ev.ts}-${i}`} ev={ev} />
          ))}
          {pending && <TypingBubble agentName={active.name} />}
          <div ref={bottomRef} />
        </section>

        <Composer
          onSend={onSend}
          disabled={state !== "open"}
          placeholder={active.composerPlaceholder}
        />
      </section>
    </main>
  );
}

// ─── Agent picker row ─────────────────────────────────────────────────

function AgentRow({
  agent,
  active,
  unread,
  onClick,
}: {
  agent: AgentCard;
  active: boolean;
  unread: number;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "w-full text-left rounded-xl p-3 transition flex items-start gap-3 border",
        active
          ? cn(agentColorBg(agent.color), agentColorBorder(agent.color))
          : "border-transparent hover:bg-bg/60",
      )}
    >
      <span
        className={cn(
          "mt-0.5 w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0",
          active ? "bg-bg-elev" : agentColorBg(agent.color),
        )}
      >
        <span className={agentColorText(agent.color)}>{agent.icon}</span>
      </span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2">
          <span
            className={cn(
              "text-[14px] font-medium leading-none",
              active ? "text-ink" : "text-text-dim",
            )}
          >
            {agent.name}
          </span>
          {unread > 0 && (
            <span className="font-mono text-[10px] text-text-mute tabular-nums">
              {String(unread).padStart(2, "0")}
            </span>
          )}
        </div>
        <p
          className={cn(
            "text-[11px] mt-0.5 leading-snug",
            active ? "text-text-dim" : "text-text-mute",
          )}
        >
          {agent.role}
        </p>
        {active && (
          <p className="text-[10px] text-text-mute mt-1 font-mono uppercase tracking-wider">
            {agent.scope}
          </p>
        )}
      </div>
    </button>
  );
}

// Tailwind class helpers — keep static so JIT picks them up
function agentColorBg(c: AgentCard["color"]): string {
  return {
    ui: "bg-ui/10",
    whatsapp: "bg-whatsapp/10",
    voice: "bg-voice/10",
    warn: "bg-warn/10",
  }[c];
}
function agentColorText(c: AgentCard["color"]): string {
  return {
    ui: "text-ui",
    whatsapp: "text-whatsapp",
    voice: "text-voice",
    warn: "text-warn",
  }[c];
}
function agentColorBorder(c: AgentCard["color"]): string {
  return {
    ui: "border-ui/30",
    whatsapp: "border-whatsapp/30",
    voice: "border-voice/30",
    warn: "border-warn/30",
  }[c];
}

// ─── Channels list ────────────────────────────────────────────────────

function ChannelRow({
  icon,
  label,
  count,
  color,
  target,
}: {
  icon: React.ReactNode;
  label: string;
  count: number;
  color: "whatsapp" | "voice" | "ui";
  target?: string | null;
}) {
  const dot = { whatsapp: "bg-whatsapp", voice: "bg-voice", ui: "bg-ui" }[color];
  return (
    <div className="py-2 group">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3 text-[13px] text-text-dim group-hover:text-text transition-colors">
          <span className={`w-1.5 h-1.5 rounded-full ${dot}`} />
          <span className="text-text-mute">{icon}</span>
          {label}
        </div>
        <span className="font-mono text-[11px] text-text-mute tabular-nums">
          {String(count).padStart(2, "0")}
        </span>
      </div>
      {target && (
        <p className="ml-6 mt-0.5 font-mono text-[10px] text-text-mute truncate">
          → {target}
        </p>
      )}
    </div>
  );
}

function TypingBubble({ agentName }: { agentName: string }) {
  return (
    <div
      className="flex w-full mb-5 justify-start fade-in"
      role="status"
      aria-label={`${agentName} is typing`}
    >
      <div className="max-w-[72%] flex flex-col gap-1.5 items-start">
        <div className="flex items-center gap-2 px-1">
          <span className="font-mono text-[10px] text-text-mute uppercase tracking-[0.18em]">
            {agentName} is typing
          </span>
        </div>
        <div className="bg-bg-elev border border-border rounded-3xl rounded-bl-md shadow-card px-5 py-3.5">
          <div className="flex items-center gap-1.5" aria-hidden="true">
            <span className="typing-dot" />
            <span className="typing-dot" style={{ animationDelay: "150ms" }} />
            <span className="typing-dot" style={{ animationDelay: "300ms" }} />
          </div>
        </div>
      </div>
    </div>
  );
}

function Suggestion({
  text,
  onSend,
}: {
  text: string;
  onSend: (body: string) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onSend(text)}
      className="w-full text-left text-[14px] text-text-dim bg-bg-elev border border-border rounded-2xl px-5 py-3.5 hover:border-border-strong hover:text-ink transition cursor-pointer shadow-soft"
    >
      {text}
    </button>
  );
}
