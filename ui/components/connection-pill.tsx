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
        "inline-flex items-center gap-1.5 text-[11px] px-2.5 py-1 rounded-full font-medium",
        s.cls,
      )}
    >
      <span className="w-1.5 h-1.5 rounded-full bg-current" />
      {s.label}
    </span>
  );
}
