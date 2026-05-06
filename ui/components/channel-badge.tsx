import { Activity, Globe, MessageCircle, Phone } from "lucide-react";
import { cn } from "@/lib/cn";

const TONE: Record<string, string> = {
  whatsapp: "bg-whatsapp/10 text-whatsapp",
  voice: "bg-voice/10 text-voice",
  ui: "bg-ui/10 text-ui",
  system: "bg-warn/12 text-warn",
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
        "inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-[0.18em] px-2 py-0.5 rounded-full font-medium",
        TONE[channel] || "bg-border text-text-mute",
      )}
    >
      {ICON[channel]}
      {LABEL[channel] || channel}
    </span>
  );
}
