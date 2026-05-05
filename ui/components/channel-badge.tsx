import { Globe, MessageCircle, Phone, Activity } from "lucide-react";
import { cn } from "@/lib/cn";

const TONE: Record<string, string> = {
  whatsapp: "bg-whatsapp/15 text-whatsapp border-whatsapp/30",
  voice: "bg-voice/15 text-voice border-voice/30",
  ui: "bg-ui/15 text-ui border-ui/30",
  system: "bg-warn/15 text-warn border-warn/30",
};

const LABEL: Record<string, string> = {
  whatsapp: "WhatsApp",
  voice: "Voice",
  ui: "Web",
  system: "Status",
};

const ICON: Record<string, React.ReactNode> = {
  whatsapp: <MessageCircle size={9} />,
  voice: <Phone size={9} />,
  ui: <Globe size={9} />,
  system: <Activity size={9} />,
};

export function ChannelBadge({ channel }: { channel: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded border font-medium",
        TONE[channel] || "bg-border/40 text-text-mute border-border",
      )}
    >
      {ICON[channel]}
      {LABEL[channel] || channel}
    </span>
  );
}
