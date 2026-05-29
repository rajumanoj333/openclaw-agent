/**
 * REST client for the FastAPI backend.
 *
 * In dev: NEXT_PUBLIC_API_URL = http://localhost:8080  (or your ngrok URL)
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

function authHeaders(): HeadersInit {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      // ngrok free tier shows an interstitial HTML page on first request.
      // Sending any value for this header bypasses it.
      "ngrok-skip-browser-warning": "1",
      ...authHeaders(),
      ...(init?.headers || {}),
    },
  });
  if (!r.ok) {
    const text = await r.text().catch(() => "");
    throw new Error(`${r.status} ${text || r.statusText}`);
  }
  return (await r.json()) as T;
}

export interface LoginResp {
  token: string;
  phone: string;
  expires_in: number;
}

export type OnboardingStep = "scrape" | "confirm" | "agent" | "ready";

export interface OnboardingStatus {
  phone: string;
  has_profile: boolean;
  profile_confirmed: boolean;
  has_agent: boolean;
  step: OnboardingStep;
}

export interface BrandKit {
  primary_color: string | null;
  secondary_color: string | null;
  accent_color: string | null;
  tone: string | null;
  visual_style: string | null;
  logo_description: string | null;
  tagline: string | null;
}

export interface BusinessProfileT {
  phone: string;
  name: string | null;
  type: string | null;
  category: string | null;
  description: string | null;
  address: string | null;
  city: string | null;
  contact_phone: string | null;
  email: string | null;
  website: string | null;
  socials: Record<string, string>;
  timings: string | null;
  services: string[];
  pricing_note: string | null;
  logo_url: string | null;
  brand: BrandKit;
  confidence: string;
  source_urls: string[];
  raw_colors: string[];
  created_at: number;
  confirmed: boolean;
}

export interface AgentCfg {
  phone: string;
  name: string;
  capabilities: string[];
  enabled_agents: string[];
  agents?: Array<{
    slug: string;
    name: string;
    role: string;
    icon: string;
    color: string;
    scope: string[];
  }>;
  persona_extra: string;
  created_at: number;
  updated_at: number;
}

export const api = {
  login: (phone: string) =>
    req<LoginResp>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ phone }),
    }),

  onboardingStatus: () => req<OnboardingStatus>("/onboarding/status"),

  capabilities: () => req<{ capabilities: string[] }>("/onboarding/capabilities"),

  scrape: (url: string) =>
    req<{ summary: string; profile: BusinessProfileT; next_step: OnboardingStep }>(
      "/onboarding/scrape",
      { method: "POST", body: JSON.stringify({ url }) },
    ),

  confirmProfile: (edits: Partial<BusinessProfileT> & {
    primary_color?: string | null;
    secondary_color?: string | null;
    accent_color?: string | null;
    tone?: string | null;
    visual_style?: string | null;
    tagline?: string | null;
  }) =>
    req<{ ok: boolean; profile: BusinessProfileT; next_step: OnboardingStep }>(
      "/onboarding/confirm",
      { method: "POST", body: JSON.stringify(edits) },
    ),

  saveAgent: (name: string, capabilities: string[], persona_extra = "") =>
    req<{ ok: boolean; agent: AgentCfg; next_step: OnboardingStep }>(
      "/onboarding/agent",
      {
        method: "POST",
        body: JSON.stringify({ name, capabilities, persona_extra }),
      },
    ),

  getProfile: () => req<BusinessProfileT>("/onboarding/profile"),

  getAgent: () => req<AgentCfg>("/onboarding/agent"),

  reset: () =>
    req<{ ok: boolean; next_step: OnboardingStep }>("/onboarding/reset", {
      method: "POST",
    }),

  reprime: () =>
    req<{ ok: boolean }>("/onboarding/reprime", { method: "POST" }),

  // ─── Instagram (via Composio) ─────────────────────────────────────────
  igStatus: () =>
    req<{
      connected: boolean;
      username?: string;
      name?: string;
      followers_count?: number;
      media_count?: number;
      ig_user_id?: string;
      error?: string;
    }>("/instagram/status"),

  igPublish: (imageUrl: string, caption: string) =>
    req<{ post_id: string; permalink: string | null; ms: number }>(
      "/instagram/publish",
      {
        method: "POST",
        body: JSON.stringify({ image_url: imageUrl, caption }),
      },
    ),

  igRecent: () =>
    req<{ items: Array<{ id: string; permalink: string; media_url: string; caption?: string; like_count?: number }> }>(
      "/instagram/recent",
    ),

  // ─── System health ──────────────────────────────────────────────────
  systemStatus: (phone?: string) =>
    req<{
      overall: "ok" | "warn" | "down";
      services: Array<{
        name: string;
        status: "ok" | "warn" | "down";
        latency_ms: number;
        detail: string;
      }>;
    }>(`/system/status${phone ? `?phone=${encodeURIComponent(phone)}` : ""}`),

  channels: () =>
    req<{ whatsapp: string | null; voice: string | null; demo_mode: boolean }>(
      "/system/channels",
    ),
};
