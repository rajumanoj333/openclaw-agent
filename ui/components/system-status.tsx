"use client";

import { Activity, ChevronDown, ChevronUp } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";

type ServiceStatus = "ok" | "warn" | "down";

interface Service {
  name: string;
  status: ServiceStatus;
  latency_ms: number;
  detail: string;
}

interface Snapshot {
  overall: ServiceStatus;
  services: Service[];
}

// Human-friendly labels. The backend ships snake_case keys; map for display.
const LABEL: Record<string, string> = {
  fastapi: "API",
  ngrok: "Tunnel",
  openclaw_proxy: "OpenClaw VM",
  twilio: "Twilio",
  gemini: "Gemini",
  pollinations: "Pollinations",
  sarvam: "Sarvam",
  composio: "Instagram",
  openclaw_primed: "Agent primed",
};

const POLL_MS = 15_000;

export function SystemStatus({ phone }: { phone?: string }) {
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const fetchOnce = async () => {
      try {
        const r = await api.systemStatus(phone);
        if (!cancelled) {
          setSnap(r);
          setLoading(false);
        }
      } catch {
        if (!cancelled) setLoading(false);
      }
    };
    fetchOnce();
    const id = setInterval(fetchOnce, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [phone]);

  const overallColor = overallDotColor(snap?.overall ?? "down");
  const overallLabel = snap
    ? snap.overall === "ok"
      ? "all systems go"
      : snap.overall === "warn"
        ? "degraded"
        : "outage"
    : loading
      ? "checking…"
      : "offline";

  return (
    <div className="border-t border-border">
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full px-7 py-3.5 flex items-center justify-between text-left hover:bg-bg/50 transition"
      >
        <div className="flex items-center gap-2.5">
          <span
            className={cn("w-2 h-2 rounded-full", overallColor)}
            style={{
              animation:
                snap?.overall === "warn" ? "pulseDot 1.4s ease-in-out infinite" : undefined,
            }}
          />
          <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-text-mute">
            System
          </span>
          <span className="text-[12px] text-text-dim">{overallLabel}</span>
        </div>
        {open ? (
          <ChevronUp size={14} className="text-text-mute" />
        ) : (
          <ChevronDown size={14} className="text-text-mute" />
        )}
      </button>

      {open && snap && (
        <ul className="px-7 pb-4 space-y-1.5">
          {snap.services.map((svc) => (
            <li
              key={svc.name}
              className="flex items-center justify-between gap-2 text-[12px]"
              title={`${svc.detail} · ${svc.latency_ms}ms`}
            >
              <div className="flex items-center gap-2 min-w-0">
                <span className={cn("w-1.5 h-1.5 rounded-full flex-shrink-0", dotColor(svc.status))} />
                <span className="text-text-dim truncate">{LABEL[svc.name] ?? svc.name}</span>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                <span className="font-mono text-[10px] text-text-mute tabular-nums">
                  {svc.latency_ms}ms
                </span>
                {svc.status !== "ok" && (
                  <span
                    className={cn(
                      "font-mono text-[10px] uppercase tracking-wider",
                      svc.status === "warn" ? "text-warn" : "text-danger",
                    )}
                  >
                    {svc.status}
                  </span>
                )}
              </div>
            </li>
          ))}
          <li className="pt-2 mt-1 border-t border-border/60 flex items-center gap-1.5 text-[10px] text-text-mute font-mono uppercase tracking-wider">
            <Activity size={10} />
            <span>refresh {POLL_MS / 1000}s</span>
          </li>
        </ul>
      )}
    </div>
  );
}

function dotColor(s: ServiceStatus): string {
  if (s === "ok") return "bg-whatsapp";
  if (s === "warn") return "bg-warn";
  return "bg-danger";
}

function overallDotColor(s: ServiceStatus): string {
  return dotColor(s);
}
