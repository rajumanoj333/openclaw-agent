"use client";

import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { getPhone } from "@/lib/api";
import { openChatSocket, type ChatEvent } from "@/lib/ws";
import { cn } from "@/lib/cn";

const STATUS_LABEL: Record<string, string> = {
  scraping: "Scraping your website…",
  scrape_done: "Scrape complete — running AI extraction",
  profile_confirmed: "Profile saved ✓",
  agent_ready: "Agent ready ✓",
  designing: "Designing your poster…",
};

/**
 * Tiny pill that listens to the WebSocket bus and shows the latest
 * status event. Used on onboarding pages so the user sees progress
 * during long-running OpenClaw calls.
 */
export function LiveStatus({ className }: { className?: string }) {
  const [status, setStatus] = useState<string | null>(null);
  const [body, setBody] = useState<string | null>(null);

  useEffect(() => {
    const phone = getPhone();
    if (!phone) return;
    const sock = openChatSocket(phone, (ev: ChatEvent) => {
      if (ev.kind === "status" && ev.status) {
        setStatus(ev.status);
        setBody(ev.body || null);
      }
    });
    return () => sock.close();
  }, []);

  if (!status) return null;

  const label = STATUS_LABEL[status] || status.replace(/_/g, " ");

  return (
    <div
      className={cn(
        "inline-flex items-center gap-2 text-xs text-warn bg-warn/10 border border-warn/30 px-3 py-1.5 rounded-full fade-in",
        className,
      )}
    >
      <Loader2 size={12} className="animate-spin" />
      <span>{label}</span>
      {body && (
        <span className="text-text-mute truncate max-w-[200px]">— {body}</span>
      )}
    </div>
  );
}
