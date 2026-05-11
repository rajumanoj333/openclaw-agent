"use client";

import {
  Activity,
  Globe,
  LogOut,
  MessageCircle,
  Phone,
  RotateCcw,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { Composer } from "@/components/composer";
import { ConnectionPill } from "@/components/connection-pill";
import { MessageBubble } from "@/components/message-bubble";
import { SystemStatus } from "@/components/system-status";
import {
  api,
  clearAuth,
  getPhone,
  getToken,
  type AgentCfg,
  type BusinessProfileT,
} from "@/lib/api";
import { openChatSocket, type ChatEvent, type ChatSocket } from "@/lib/ws";

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
  const sockRef = useRef<ChatSocket | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const pendingTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

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
        api.getAgent().then(setAgent).catch(() => {});
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
              // Any agent reply (direction === "out") clears the pending dots.
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

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events.length, pending]);

  if (!phone) return null;

  const onSend = (body: string) => {
    setEvents((cur) => [
      ...cur,
      {
        phone: phone!,
        channel: "ui",
        direction: "in",
        body,
        kind: "message",
        ts: Date.now() / 1000,
      } as ChatEvent,
    ]);
    sockRef.current?.send(body);
    setPending(true);
    // Fail-safe: drop the typing indicator after 5min in case WS misses the
    // reply event (network blip, server restart mid-call, etc).
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
      /* ignore — even if server fails, push them through */
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

  const agentName = agent?.name || "Morpheus";
  const businessName = profile?.name;

  return (
    <main className="h-screen flex">
      {/* SIDEBAR */}
      <aside className="w-80 hidden md:flex flex-col border-r border-border bg-bg-elev/60 backdrop-blur-xl">
        <div className="p-7 pb-6 border-b border-border">
          <div className="rule mb-5">
            <span>The Studio</span>
          </div>
          <h2 className="font-display text-[34px] leading-[1.05] text-ink italic font-medium tracking-editorial">
            {agentName}
          </h2>
          <p className="mt-1.5 text-[12px] text-text-mute font-mono uppercase tracking-[0.18em]">
            marketing employee
          </p>

          <div className="mt-5">
            {!profileLoaded ? (
              <div className="space-y-2">
                <div className="skeleton h-3 w-2/3" />
                <div className="skeleton h-3 w-1/2" />
              </div>
            ) : businessName ? (
              <p className="text-[14px] text-text-dim leading-relaxed">
                Acting for{" "}
                <span
                  className="font-medium"
                  style={{ color: "hsl(220 30% 8%)" }}
                >
                  {businessName}
                </span>
                {profile?.brand?.tone && (
                  <>
                    <span className="text-text-mute"> · </span>
                    <span className="text-text-mute">
                      {profile.brand.tone}
                    </span>
                  </>
                )}
              </p>
            ) : (
              <div className="text-[13px] leading-relaxed">
                <p className="text-warn font-medium mb-1">
                  Profile lost on server restart
                </p>
                <button
                  onClick={() => router.replace("/onboarding")}
                  className="font-mono text-[11px] uppercase tracking-[0.18em] text-text-dim hover:text-text underline underline-offset-4"
                >
                  re-link →
                </button>
              </div>
            )}
          </div>

          {profile?.brand && (
            <div className="flex gap-1.5 mt-4">
              {[
                profile.brand.primary_color,
                profile.brand.secondary_color,
                profile.brand.accent_color,
              ]
                .filter(Boolean)
                .map((c) => (
                  <span
                    key={c}
                    className="w-6 h-6 rounded-md border border-border shadow-soft"
                    style={{ backgroundColor: c! }}
                    title={c!}
                  />
                ))}
            </div>
          )}
        </div>

        <div className="p-7 border-b border-border">
          <h3 className="font-mono text-[10px] uppercase tracking-[0.2em] text-text-mute mb-4">
            Channels
          </h3>
          <ChannelRow
            icon={<MessageCircle size={14} />}
            label="WhatsApp"
            count={counts.whatsapp || 0}
            color="whatsapp"
          />
          <ChannelRow
            icon={<Phone size={14} />}
            label="Voice"
            count={counts.voice || 0}
            color="voice"
          />
          <ChannelRow
            icon={<Globe size={14} />}
            label="Web"
            count={counts.ui || 0}
            color="ui"
          />
        </div>

        {agent && agent.capabilities.length > 0 && (
          <div className="p-7 border-b border-border">
            <h3 className="font-mono text-[10px] uppercase tracking-[0.2em] text-text-mute mb-4">
              Scope
            </h3>
            <div className="flex flex-wrap gap-1.5">
              {agent.capabilities.map((c) => (
                <span key={c} className="tag">
                  {c.replace(/_/g, " ")}
                </span>
              ))}
            </div>
          </div>
        )}

        <SystemStatus phone={phone} />

        <div className="mt-auto p-7 space-y-2">
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
          <p className="font-mono text-[11px] text-text-mute text-center mt-3 tracking-wider">
            {phone}
          </p>
        </div>
      </aside>

      {/* MAIN */}
      <section className="flex-1 flex flex-col min-w-0">
        <header className="flex items-end justify-between px-8 py-5 border-b border-border bg-bg-elev/40 backdrop-blur-xl">
          <div>
            <h1 className="font-display text-[26px] italic leading-none text-ink tracking-editorial">
              {agentName}
            </h1>
            <p className="mt-1.5 text-[12px] text-text-mute font-mono">
              {businessName ? (
                <>acting for {businessName.toLowerCase()}</>
              ) : (
                phone
              )}
            </p>
          </div>
          <ConnectionPill state={state} />
        </header>

        {activeStatus && (
          <div className="px-8 py-3 border-b border-border bg-warn/5">
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

        <section className="flex-1 overflow-y-auto px-8 py-8">
          {events.length === 0 && !activeStatus && (
            <div className="h-full flex items-center justify-center text-center">
              <div className="max-w-xl">
                <div className="relative inline-block mb-7 rise" style={{ animationDelay: "60ms" }}>
                  <div className="w-36 h-36 mx-auto blob" />
                  <span
                    aria-hidden
                    className="absolute inset-0 flex items-center justify-center font-display italic text-[64px] text-ink/85 tracking-editorial"
                  >
                    M
                  </span>
                </div>
                <h2
                  className="font-display italic text-[40px] leading-[1.05] text-ink tracking-editorial mb-4 rise"
                  style={{ animationDelay: "180ms" }}
                >
                  Hey — I'm {agentName}.
                </h2>
                <p
                  className="text-[15px] text-text-dim leading-relaxed mb-8 max-w-md mx-auto rise"
                  style={{ animationDelay: "300ms" }}
                >
                  Send me a message here, on WhatsApp, or call. Everything syncs
                  to one thread in real time.
                </p>
                <div
                  className="grid gap-2 text-left rise"
                  style={{ animationDelay: "420ms" }}
                >
                  <Suggestion text="make me a poster for diwali sale" />
                  <Suggestion text="what's our brand tone?" />
                  <Suggestion text="draft an instagram caption for new admission" />
                </div>
              </div>
            </div>
          )}
          {events.map((ev, i) => (
            <MessageBubble key={`${ev.ts}-${i}`} ev={ev} />
          ))}
          {pending && <TypingBubble agentName={agentName} />}
          <div ref={bottomRef} />
        </section>

        <Composer onSend={onSend} disabled={state !== "open"} />
      </section>
    </main>
  );
}

function ChannelRow({
  icon,
  label,
  count,
  color,
}: {
  icon: React.ReactNode;
  label: string;
  count: number;
  color: "whatsapp" | "voice" | "ui";
}) {
  const dot = {
    whatsapp: "bg-whatsapp",
    voice: "bg-voice",
    ui: "bg-ui",
  }[color];
  return (
    <div className="flex items-center justify-between py-2 group">
      <div className="flex items-center gap-3 text-[14px] text-text-dim group-hover:text-text transition-colors">
        <span className={`w-1.5 h-1.5 rounded-full ${dot}`} />
        <span className="text-text-mute">{icon}</span>
        {label}
      </div>
      <span className="font-mono text-[12px] text-text-mute tabular-nums">
        {String(count).padStart(2, "0")}
      </span>
    </div>
  );
}

function TypingBubble({ agentName }: { agentName: string }) {
  return (
    <div className="flex w-full mb-5 justify-start fade-in">
      <div className="max-w-[72%] flex flex-col gap-1.5 items-start">
        <div className="flex items-center gap-2 px-1">
          <span className="font-mono text-[10px] text-text-mute uppercase tracking-[0.18em]">
            {agentName} is typing
          </span>
        </div>
        <div className="bg-bg-elev border border-border rounded-3xl rounded-bl-md shadow-card px-5 py-3.5">
          <div className="flex items-center gap-1.5">
            <span className="typing-dot" />
            <span className="typing-dot" style={{ animationDelay: "150ms" }} />
            <span className="typing-dot" style={{ animationDelay: "300ms" }} />
          </div>
        </div>
      </div>
    </div>
  );
}

function Suggestion({ text }: { text: string }) {
  return (
    <div className="text-[14px] text-text-dim bg-bg-elev border border-border rounded-2xl px-5 py-3.5 hover:border-border-strong hover:text-ink transition cursor-default shadow-soft">
      {text}
    </div>
  );
}
