import { cn } from "@/lib/cn";

const STATE: Record<string, { label: string; cls: string }> = {
  open: { label: "Live", cls: "bg-whatsapp/12 text-whatsapp" },
  connecting: { label: "Connecting", cls: "bg-warn/12 text-warn pulse-dot" },
  closed: { label: "Offline", cls: "bg-border text-text-mute" },
  error: { label: "Error", cls: "bg-danger/12 text-danger" },
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
        "inline-flex items-center gap-1.5 font-mono text-[10px] uppercase px-2.5 py-1 rounded-full font-medium tracking-[0.16em]",
        s.cls,
      )}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-current" />
      {s.label}
    </span>
  );
}
