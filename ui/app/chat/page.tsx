"use client";

import { LogOut, Sparkles, Phone, MessageCircle, Globe, Activity } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { Composer } from "@/components/composer";
import { ConnectionPill } from "@/components/connection-pill";
import { MessageBubble } from "@/components/message-bubble";
import { api, clearAuth, getPhone, getToken, type AgentCfg, type BusinessProfileT } from "@/lib/api";
import { openChatSocket, type ChatEvent, type ChatSocket } from "@/lib/ws";

export default function ChatPage() {
  const router = useRouter();
  const [events, setEvents] = useState<ChatEvent[]>([]);
  const [state, setState] = useState<"connecting" | "open" | "closed" | "error">(
    "connecting",
  );
  const [agent, setAgent] = useState<AgentCfg | null>(null);
  const [profile, setProfile] = useState<BusinessProfileT | null>(null);
  const [activeStatus, setActiveStatus] = useState<{ status: string; body?: string } | null>(null);
  const sockRef = useRef<ChatSocket | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

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
        api.getProfile().then(setProfile).catch(() => {});
        const sock = openChatSocket(
          phone,
          (ev) => {
            if (ev.kind === "status") {
              setActiveStatus({
                status: ev.status || "working",
                body: ev.body || undefined,
              });
              // auto-clear status after 6 sec for terminal states
              if (
                ev.status?.endsWith("_done") ||
                ev.status === "agent_ready" ||
                ev.status === "profile_confirmed"
              ) {
                setTimeout(() => setActiveStatus(null), 6000);
              }
            } else {
              setEvents((cur) => [...cur, ev]);
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
  }, [events.length]);

  if (!phone) return null;

  const onSend = (body: string) => {
    // Optimistically paint the user's outgoing UI message so they see it
    // immediately without waiting for a server roundtrip / broadcast.
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
  };

  const logout = () => {
    sockRef.current?.close();
    clearAuth();
    router.replace("/login");
  };

  // channel summary for sidebar
  const counts = events.reduce(
    (acc, ev) => {
      const k = ev.channel === "system" ? "ui" : ev.channel;
      acc[k] = (acc[k] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>,
  );

  return (
    <main className="h-screen flex bg-bg">
      {/* SIDEBAR */}
      <aside className="w-72 hidden md:flex flex-col border-r border-border bg-bg-elev/60 backdrop-blur">
        <div className="p-5 border-b border-border">
          <div className="flex items-center gap-2.5 mb-3">
            <div className="w-9 h-9 rounded-xl bg-accent/20 border border-accent/40 flex items-center justify-center">
              <Sparkles size={18} className="text-accent" />
            </div>
            <div>
              <h2 className="font-semibold text-sm leading-tight">
                {agent?.name || "Morpheus"}
              </h2>
              <p className="text-[11px] text-text-mute">marketing agent</p>
            </div>
          </div>
          <p className="text-xs text-text-dim leading-relaxed">
            {profile?.name || "Loading…"}
          </p>
          {profile?.brand?.tone && (
            <p className="text-[11px] text-text-mute mt-1">
              Tone: {profile.brand.tone}
            </p>
          )}
          {profile?.brand && (
            <div className="flex gap-1.5 mt-3">
              {[profile.brand.primary_color, profile.brand.secondary_color, profile.brand.accent_color]
                .filter(Boolean)
                .map((c) => (
                  <span
                    key={c}
                    className="w-5 h-5 rounded-md border border-border"
                    style={{ backgroundColor: c! }}
                    title={c!}
                  />
                ))}
            </div>
          )}
        </div>

        <div className="p-5 border-b border-border">
          <h3 className="text-[10px] uppercase tracking-wider text-text-mute mb-3 font-semibold">
            Channels
          </h3>
          <ChannelRow icon={<MessageCircle size={14} />} label="WhatsApp" count={counts.whatsapp || 0} color="whatsapp" />
          <ChannelRow icon={<Phone size={14} />} label="Voice" count={counts.voice || 0} color="voice" />
          <ChannelRow icon={<Globe size={14} />} label="Web UI" count={counts.ui || 0} color="ui" />
        </div>

        {agent && (
          <div className="p-5 border-b border-border">
            <h3 className="text-[10px] uppercase tracking-wider text-text-mute mb-3 font-semibold">
              Capabilities
            </h3>
            <div className="flex flex-wrap gap-1">
              {agent.capabilities.map((c) => (
                <span
                  key={c}
                  className="text-[10px] bg-accent/10 text-accent border border-accent/30 px-2 py-0.5 rounded-full"
                >
                  {c.replace(/_/g, " ")}
                </span>
              ))}
            </div>
          </div>
        )}

        <div className="mt-auto p-5">
          <button
            onClick={logout}
            className="w-full flex items-center justify-center gap-2 text-xs text-text-mute hover:text-text border border-border hover:border-border-strong rounded-lg py-2 transition"
          >
            <LogOut size={12} />
            Sign out
          </button>
          <p className="text-[10px] text-text-mute text-center mt-2">{phone}</p>
        </div>
      </aside>

      {/* MAIN */}
      <section className="flex-1 flex flex-col min-w-0">
        <header className="flex items-center justify-between px-5 py-3.5 border-b border-border bg-bg-elev/40">
          <div>
            <h1 className="text-sm font-semibold">{agent?.name || "Morpheus"}</h1>
            <p className="text-xs text-text-mute">
              {profile?.name ? `Acting for ${profile.name}` : phone}
            </p>
          </div>
          <ConnectionPill state={state} />
        </header>

        {activeStatus && (
          <div className="px-5 py-2 border-b border-border bg-warn/5">
            <div className="inline-flex items-center gap-2 text-xs text-warn">
              <Activity size={12} className="pulse-dot" />
              <span className="capitalize">
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

        <section className="flex-1 overflow-y-auto px-5 py-5">
          {events.length === 0 && !activeStatus && (
            <div className="h-full flex items-center justify-center text-center px-6">
              <div className="max-w-md fade-in">
                <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-accent/15 border border-accent/40 flex items-center justify-center">
                  <Sparkles size={24} className="text-accent" />
                </div>
                <h3 className="text-base font-semibold mb-2">
                  Hey, I'm {agent?.name || "Morpheus"} 👋
                </h3>
                <p className="text-sm text-text-dim leading-relaxed mb-6">
                  Try sending me a message in any channel. I'll keep WhatsApp,
                  voice calls, and this web view in sync.
                </p>
                <div className="grid gap-2 text-left">
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
    <div className="flex items-center justify-between py-1.5">
      <div className="flex items-center gap-2.5 text-sm text-text-dim">
        <span className={`w-1.5 h-1.5 rounded-full ${dot}`} />
        {icon}
        {label}
      </div>
      <span className="text-[11px] text-text-mute tabular-nums">{count}</span>
    </div>
  );
}

function Suggestion({ text }: { text: string }) {
  return (
    <div className="text-xs text-text-dim bg-panel/60 border border-border rounded-lg px-3 py-2 hover:border-border-strong transition cursor-default">
      "{text}"
    </div>
  );
}
