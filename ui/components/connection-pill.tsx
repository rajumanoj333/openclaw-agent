import { cn } from "@/lib/cn";

const STATE_TONE: Record<string, string> = {
  open: "bg-whatsapp/20 text-whatsapp",
  connecting: "bg-warn/20 text-warn animate-pulse",
  closed: "bg-border/40 text-white/50",
  error: "bg-red-500/30 text-red-300",
};

export function ConnectionPill({
  state,
}: {
  state: "connecting" | "open" | "closed" | "error";
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full",
        STATE_TONE[state],
      )}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-current" />
      {state}
    </span>
  );
}
