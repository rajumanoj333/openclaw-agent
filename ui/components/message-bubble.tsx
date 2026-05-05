import { cn } from "@/lib/cn";
import type { ChatEvent } from "@/lib/ws";
import { ChannelBadge } from "./channel-badge";

export function MessageBubble({ ev }: { ev: ChatEvent }) {
  const isOut = ev.direction === "out";
  const isStatus = ev.kind === "status";

  if (isStatus) {
    return (
      <div className="flex justify-center my-2">
        <div className="inline-flex items-center gap-2 text-xs text-warn bg-warn/10 border border-warn/30 px-3 py-1 rounded-full">
          <span className="animate-pulse">●</span>
          <span className="capitalize">{ev.status?.replace(/_/g, " ")}</span>
          {ev.body && <span className="opacity-70 truncate max-w-[300px]">— {ev.body}</span>}
        </div>
      </div>
    );
  }

  return (
    <div className={cn("flex w-full mb-3", isOut ? "justify-start" : "justify-end")}>
      <div className={cn("max-w-[78%] flex flex-col gap-1", isOut ? "items-start" : "items-end")}>
        <div className="flex items-center gap-2">
          <ChannelBadge channel={ev.channel} />
          {ev.lang && (
            <span className="text-[10px] text-white/40">{ev.lang}</span>
          )}
        </div>
        <div
          className={cn(
            "px-3 py-2 rounded-2xl text-sm leading-relaxed border",
            isOut
              ? "bg-panel border-border text-white/90 rounded-bl-sm"
              : "bg-accent/15 border-accent/40 text-white rounded-br-sm",
          )}
        >
          {ev.body && <p className="whitespace-pre-wrap break-words">{ev.body}</p>}
          {ev.media_url && (
            <div className="mt-2">
              {/* Use native img — Next/Image has remote-pattern friction in dev */}
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={ev.media_url}
                alt="media"
                className="rounded-lg max-h-72 border border-border"
              />
              <a
                href={ev.media_url}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-1 text-[10px] text-accent underline-offset-2 hover:underline block"
              >
                open
              </a>
            </div>
          )}
        </div>
        <span className="text-[10px] text-white/30">
          {new Date(ev.ts * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
        </span>
      </div>
    </div>
  );
}
