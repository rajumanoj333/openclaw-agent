import { cn } from "@/lib/cn";
import type { ChatEvent } from "@/lib/ws";
import { ChannelBadge } from "./channel-badge";

export function MessageBubble({ ev }: { ev: ChatEvent }) {
  const isOut = ev.direction === "out";

  return (
    <div className={cn("flex w-full mb-4 fade-in", isOut ? "justify-start" : "justify-end")}>
      <div className={cn("max-w-[75%] flex flex-col gap-1.5", isOut ? "items-start" : "items-end")}>
        <div className="flex items-center gap-2">
          <ChannelBadge channel={ev.channel} />
          {ev.lang && (
            <span className="text-[10px] text-text-mute font-mono">{ev.lang}</span>
          )}
        </div>
        <div
          className={cn(
            "px-3.5 py-2.5 rounded-2xl text-sm leading-relaxed border shadow-sm",
            isOut
              ? "bg-panel border-border text-text rounded-bl-md"
              : "bg-accent/15 border-accent/40 text-text rounded-br-md",
          )}
        >
          {ev.body && <p className="whitespace-pre-wrap break-words">{ev.body}</p>}
          {ev.media_url && (
            <div className="mt-2.5">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={`/api/img?url=${encodeURIComponent(ev.media_url)}`}
                alt="media"
                className="rounded-lg max-h-72 border border-border"
              />
              <a
                href={`/api/img?url=${encodeURIComponent(ev.media_url)}`}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-1.5 text-[11px] text-accent hover:underline block"
              >
                open ↗
              </a>
            </div>
          )}
        </div>
        <span className="text-[10px] text-text-mute tabular-nums">
          {new Date(ev.ts * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
        </span>
      </div>
    </div>
  );
}
