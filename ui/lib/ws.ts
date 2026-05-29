import { WS_URL } from "./api";

export interface ChatEvent {
  phone: string;
  channel: "whatsapp" | "voice" | "ui" | "system";
  direction: "in" | "out";
  body?: string | null;
  media_url?: string | null;
  lang?: string | null;
  kind: "message" | "status" | "task";
  status?: string | null;
  agent_slug?: string | null;     // which agent generated or was addressed
  meta?: Record<string, unknown>;
  ts: number;
}

export type EventHandler = (ev: ChatEvent) => void;

export interface ChatSocket {
  send: (body: string, agentSlug?: string) => void;
  close: () => void;
}

/**
 * Open a WebSocket to /ws/{phone}. Reconnects with exponential backoff.
 * Returns an object with a .close() to tear down.
 */
export function openChatSocket(
  phone: string,
  onEvent: EventHandler,
  onState?: (s: "connecting" | "open" | "closed" | "error") => void,
): ChatSocket {
  let ws: WebSocket | null = null;
  let closedByUser = false;
  let attempts = 0;
  let backoffTimer: ReturnType<typeof setTimeout> | null = null;

  const connect = () => {
    onState?.("connecting");
    ws = new WebSocket(`${WS_URL}/ws/${encodeURIComponent(phone)}`);

    ws.onopen = () => {
      attempts = 0;
      onState?.("open");
    };

    ws.onmessage = (m) => {
      try {
        const ev = JSON.parse(m.data) as ChatEvent;
        onEvent(ev);
      } catch {
        /* ignore malformed frames */
      }
    };

    ws.onerror = () => onState?.("error");

    ws.onclose = () => {
      onState?.("closed");
      if (closedByUser) return;
      const delay = Math.min(30_000, 500 * 2 ** attempts++);
      backoffTimer = setTimeout(connect, delay);
    };
  };

  connect();

  return {
    send: (body: string, agentSlug?: string) => {
      if (ws?.readyState === WebSocket.OPEN) {
        const payload: Record<string, unknown> = { type: "msg", body };
        if (agentSlug) payload.agent_slug = agentSlug;
        ws.send(JSON.stringify(payload));
      }
    },
    close: () => {
      closedByUser = true;
      if (backoffTimer) clearTimeout(backoffTimer);
      ws?.close();
    },
  };
}
