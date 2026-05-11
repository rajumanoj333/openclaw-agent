"use client";

import { Instagram, Loader2 } from "lucide-react";
import { useState } from "react";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import type { ChatEvent } from "@/lib/ws";
import { ChannelBadge } from "./channel-badge";

type PublishState =
  | { kind: "idle" }
  | { kind: "publishing" }
  | { kind: "done"; permalink: string | null }
  | { kind: "error"; message: string };

export function MessageBubble({ ev }: { ev: ChatEvent }) {
  const isOut = ev.direction === "out";
  const [publish, setPublish] = useState<PublishState>({ kind: "idle" });

  const onPublish = async () => {
    if (!ev.media_url) return;
    setPublish({ kind: "publishing" });
    try {
      const r = await api.igPublish(ev.media_url, ev.body || "");
      setPublish({ kind: "done", permalink: r.permalink });
    } catch (e) {
      setPublish({ kind: "error", message: String(e) });
    }
  };

  return (
    <div
      className={cn(
        "flex w-full mb-5 fade-in",
        isOut ? "justify-start" : "justify-end",
      )}
    >
      <div
        className={cn(
          "max-w-[72%] flex flex-col gap-1.5",
          isOut ? "items-start" : "items-end",
        )}
      >
        <div className="flex items-center gap-2 px-1">
          <ChannelBadge channel={ev.channel} />
          {ev.lang && (
            <span className="font-mono text-[10px] text-text-mute uppercase tracking-wider">
              {ev.lang}
            </span>
          )}
        </div>

        <div
          className={cn(
            "px-5 py-3 text-[15px] leading-[1.55] max-w-full",
            isOut
              ? "bg-bg-elev border border-border text-text rounded-3xl rounded-bl-md shadow-card"
              : "rounded-3xl rounded-br-md shadow-ink",
          )}
          style={
            isOut
              ? undefined
              : { background: "hsl(220 30% 8%)", color: "#ffffff" }
          }
        >
          {ev.body && (
            <p className="whitespace-pre-wrap break-words">{ev.body}</p>
          )}
          {ev.media_url && (
            <div className="mt-3">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={`/api/img?url=${encodeURIComponent(ev.media_url)}`}
                alt="media"
                className="rounded-2xl max-h-80 border border-border"
              />
              <div className="flex items-center justify-between mt-2 gap-3">
                <a
                  href={`/api/img?url=${encodeURIComponent(ev.media_url)}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={cn(
                    "font-mono text-[11px] hover:underline tracking-wider uppercase",
                    isOut && "text-text-mute",
                  )}
                  style={
                    isOut ? undefined : { color: "rgba(255,255,255,0.7)" }
                  }
                >
                  open ↗
                </a>

                {/* Publish-to-Instagram button — only on agent's poster bubbles */}
                {isOut && (
                  <PublishButton state={publish} onClick={onPublish} />
                )}
              </div>

              {publish.kind === "done" && publish.permalink && (
                <a
                  href={publish.permalink}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block mt-2 font-mono text-[11px] text-whatsapp hover:underline tracking-wider uppercase"
                >
                  posted ↗ {publish.permalink.replace("https://", "")}
                </a>
              )}
              {publish.kind === "error" && (
                <p className="mt-2 font-mono text-[10px] text-danger break-all">
                  {publish.message}
                </p>
              )}
            </div>
          )}
        </div>

        <span className="font-mono text-[10px] text-text-mute tabular-nums px-1 tracking-wider">
          {new Date(ev.ts * 1000).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </span>
      </div>
    </div>
  );
}

function PublishButton({
  state,
  onClick,
}: {
  state: PublishState;
  onClick: () => void;
}) {
  if (state.kind === "publishing") {
    return (
      <span className="inline-flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-wider text-text-mute border border-border rounded-full px-2.5 py-1">
        <Loader2 size={12} className="animate-spin" />
        publishing…
      </span>
    );
  }
  if (state.kind === "done") {
    return (
      <span className="inline-flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-wider text-whatsapp border border-whatsapp/30 bg-whatsapp/5 rounded-full px-2.5 py-1">
        ✓ posted
      </span>
    );
  }
  return (
    <button
      onClick={onClick}
      className="inline-flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-wider border border-ink/15 hover:border-ink/40 hover:bg-ink/5 transition rounded-full px-2.5 py-1"
      style={{ color: "hsl(220 30% 8%)" }}
    >
      <Instagram size={13} />
      publish to instagram
    </button>
  );
}
