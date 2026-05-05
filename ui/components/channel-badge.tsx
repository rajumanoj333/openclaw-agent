import { cn } from "@/lib/cn";

const TONE: Record<string, string> = {
  whatsapp: "bg-whatsapp/20 text-whatsapp border-whatsapp/40",
  voice: "bg-voice/20 text-voice border-voice/40",
  ui: "bg-ui/20 text-ui border-ui/40",
  system: "bg-warn/20 text-warn border-warn/40",
};

const LABEL: Record<string, string> = {
  whatsapp: "WhatsApp",
  voice: "Voice",
  ui: "Web",
  system: "Status",
};

export function ChannelBadge({ channel }: { channel: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded border",
        TONE[channel] || "bg-border/40 text-white/60 border-border",
      )}
    >
      {LABEL[channel] || channel}
    </span>
  );
}
