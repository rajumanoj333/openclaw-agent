import { cn } from "@/lib/cn";
import type { ChatEvent } from "@/lib/ws";
import { ChannelBadge } from "./channel-badge";

export function MessageBubble({ ev }: { ev: ChatEvent }) {
  const isOut = ev.direction === "out";

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
              : {
                  background: "hsl(220 30% 8%)",
                  color: "#ffffff",
                }
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
              <a
                href={`/api/img?url=${encodeURIComponent(ev.media_url)}`}
                target="_blank"
                rel="noopener noreferrer"
                className={cn(
                  "mt-2 font-mono text-[11px] block hover:underline tracking-wider uppercase",
                  isOut && "text-text-mute",
                )}
                style={
                  isOut ? undefined : { color: "rgba(255,255,255,0.7)" }
                }
              >
                open ↗
              </a>
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
