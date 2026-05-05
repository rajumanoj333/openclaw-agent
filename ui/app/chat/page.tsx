"use client";

import { LogOut } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { Composer } from "@/components/composer";
import { ConnectionPill } from "@/components/connection-pill";
import { MessageBubble } from "@/components/message-bubble";
import { api, clearAuth, getPhone, getToken, type AgentCfg } from "@/lib/api";
import { openChatSocket, type ChatEvent, type ChatSocket } from "@/lib/ws";

export default function ChatPage() {
  const router = useRouter();
  const [events, setEvents] = useState<ChatEvent[]>([]);
  const [state, setState] = useState<"connecting" | "open" | "closed" | "error">(
    "connecting",
  );
  const [agent, setAgent] = useState<AgentCfg | null>(null);
  const sockRef = useRef<ChatSocket | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  const phone = useMemo(() => getPhone(), []);
  const token = useMemo(() => getToken(), []);

  useEffect(() => {
    if (!phone || !token) {
      router.replace("/login");
      return;
    }

    // Onboarding gate: chat page only opens once everything is set.
    api
      .onboardingStatus()
      .then((s) => {
        if (s.step !== "ready") {
          router.replace("/onboarding");
          return;
        }
        api.getAgent().then(setAgent).catch(() => {});
        const sock = openChatSocket(
          phone,
          (ev) => setEvents((cur) => [...cur, ev]),
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
    sockRef.current?.send(body);
  };

  const logout = () => {
    sockRef.current?.close();
    clearAuth();
    router.replace("/login");
  };

  return (
    <main className="h-screen flex flex-col">
      <header className="flex items-center justify-between px-4 py-3 border-b border-border bg-panel/60 backdrop-blur">
        <div>
          <h1 className="text-sm font-semibold">{agent?.name || "Morpheus"}</h1>
          <p className="text-xs text-white/40">
            {phone}
            {agent && agent.capabilities.length > 0 && (
              <span className="ml-2 text-white/30">
                · {agent.capabilities.length} capabilities
              </span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <ConnectionPill state={state} />
          <button
            onClick={logout}
            className="text-white/60 hover:text-white p-1"
            aria-label="Sign out"
          >
            <LogOut size={16} />
          </button>
        </div>
      </header>

      <section className="flex-1 overflow-y-auto px-4 py-4">
        {events.length === 0 && (
          <div className="text-center text-white/40 mt-12 px-6">
            <p className="text-sm">
              Send your business URL (website, Instagram, or Google Maps) to start.
            </p>
            <p className="text-xs mt-2">
              Or send a WhatsApp message to your bot — it'll appear here in real time.
            </p>
          </div>
        )}
        {events.map((ev, i) => (
          <MessageBubble key={`${ev.ts}-${i}`} ev={ev} />
        ))}
        <div ref={bottomRef} />
      </section>

      <Composer onSend={onSend} disabled={state !== "open"} />
    </main>
  );
}
