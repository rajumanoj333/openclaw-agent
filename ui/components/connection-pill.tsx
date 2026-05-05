import { cn } from "@/lib/cn";

const STATE: Record<string, { label: string; cls: string }> = {
  open: { label: "Connected", cls: "bg-whatsapp/15 text-whatsapp border-whatsapp/40" },
  connecting: { label: "Connecting…", cls: "bg-warn/15 text-warn border-warn/40 pulse-dot" },
  closed: { label: "Disconnected", cls: "bg-border/40 text-text-mute border-border" },
  error: { label: "Error", cls: "bg-danger/20 text-danger border-danger/40" },
};

export function ConnectionPill({
  state,
}: {
  state: "connecting" | "open" | "closed" | "error";
}) {
  const s = STATE[state] || STATE.closed;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 text-[10px] uppercase tracking-wider px-2 py-1 rounded-full border font-medium",
        s.cls,
      )}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-current" />
      {s.label}
    </span>
  );
}
