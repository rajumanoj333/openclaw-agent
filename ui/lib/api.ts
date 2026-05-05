/**
 * Tiny REST client for the FastAPI backend.
 *
 * In dev: NEXT_PUBLIC_API_URL = http://localhost:8080
 * In prod: NEXT_PUBLIC_API_URL = https://<your-vm-domain> or ngrok URL
 */

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080";

export const WS_URL =
  process.env.NEXT_PUBLIC_WS_URL ||
  (typeof window !== "undefined"
    ? API_URL.replace(/^http/, "ws")
    : "ws://localhost:8080");

const TOKEN_KEY = "morpheus.token";
const PHONE_KEY = "morpheus.phone";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function getPhone(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(PHONE_KEY);
}

export function saveAuth(token: string, phone: string): void {
  window.localStorage.setItem(TOKEN_KEY, token);
  window.localStorage.setItem(PHONE_KEY, phone);
}

export function clearAuth(): void {
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(PHONE_KEY);
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });
  if (!r.ok) {
    const text = await r.text().catch(() => "");
    throw new Error(`${r.status} ${text || r.statusText}`);
  }
  return (await r.json()) as T;
}

export interface StartResp {
  sent: boolean;
  phone: string;
  demo_hint?: string;
}

export interface VerifyResp {
  token: string;
  phone: string;
  expires_in: number;
}

export const api = {
  authStart: (phone: string) =>
    req<StartResp>("/auth/start", {
      method: "POST",
      body: JSON.stringify({ phone }),
    }),

  authVerify: (phone: string, code: string) =>
    req<VerifyResp>("/auth/verify", {
      method: "POST",
      body: JSON.stringify({ phone, code }),
    }),
};
