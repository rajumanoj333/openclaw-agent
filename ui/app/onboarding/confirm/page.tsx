"use client";

import { ArrowRight, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { StepIndicator } from "@/components/step-indicator";
import { api, type BusinessProfileT } from "@/lib/api";

export default function ConfirmProfilePage() {
  const router = useRouter();
  const [profile, setProfile] = useState<BusinessProfileT | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [edits, setEdits] = useState<Record<string, string>>({});

  useEffect(() => {
    api
      .getProfile()
      .then((p) => {
        if (!p.name && p.website) {
          try {
            const host = new URL(p.website).hostname.replace(/^www\./, "");
            const guess = host.split(".")[0];
            p.name = guess.charAt(0).toUpperCase() + guess.slice(1);
          } catch {
            /* ignore */
          }
        }
        setProfile(p);
      })
      .catch((e) => {
        const msg = String(e);
        if (msg.includes("404") || msg.includes("no profile")) {
          router.replace("/onboarding/business");
        } else {
          setErr(msg);
        }
      });
  }, [router]);

  const update = (k: string, v: string) =>
    setEdits((e) => ({ ...e, [k]: v }));

  const value = (k: keyof BusinessProfileT, fallback: any = "") =>
    edits[k] ?? (profile ? (profile[k] as any) ?? fallback : fallback);

  const brandValue = (k: keyof BusinessProfileT["brand"], fallback: any = "") =>
    edits[`brand.${k}`] ??
    (profile ? (profile.brand as any)[k] ?? fallback : fallback);

  const submit = async () => {
    if (!profile) return;
    setBusy(true);
    setErr(null);
    try {
      await api.confirmProfile({
        name: edits.name ?? profile.name ?? undefined,
        type: edits.type ?? profile.type ?? undefined,
        description: edits.description ?? profile.description ?? undefined,
        address: edits.address ?? profile.address ?? undefined,
        city: edits.city ?? profile.city ?? undefined,
        contact_phone: edits.contact_phone ?? profile.contact_phone ?? undefined,
        email: edits.email ?? profile.email ?? undefined,
        timings: edits.timings ?? profile.timings ?? undefined,
        services: edits.services
          ? edits.services.split(",").map((s) => s.trim()).filter(Boolean)
          : profile.services,
        primary_color:
          edits["brand.primary_color"] ?? profile.brand.primary_color ?? undefined,
        secondary_color:
          edits["brand.secondary_color"] ??
          profile.brand.secondary_color ??
          undefined,
        accent_color:
          edits["brand.accent_color"] ?? profile.brand.accent_color ?? undefined,
        tone: edits["brand.tone"] ?? profile.brand.tone ?? undefined,
        visual_style:
          edits["brand.visual_style"] ?? profile.brand.visual_style ?? undefined,
        tagline: edits["brand.tagline"] ?? profile.brand.tagline ?? undefined,
      });
      router.push("/onboarding/agent");
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  };

  if (!profile) {
    return (
      <div className="card p-8 text-center text-text-dim text-sm">
        <Loader2 className="animate-spin inline-block mr-2" size={16} />
        Loading…
      </div>
    );
  }

  const missingFields =
    !profile.name || !profile.description || profile.services.length === 0;

  return (
    <div className="card p-6 sm:p-10 fade-in">
      <StepIndicator active={1} />

      <div className="mb-7">
        <h1 className="font-display italic text-[28px] sm:text-[36px] leading-[1.05] tracking-editorial text-ink mb-2">
          Does this look right?
        </h1>
        <p className="text-[14px] text-text-dim leading-relaxed">
          Edit anything that's wrong. The agent will use exactly these details
          across every channel.
        </p>
      </div>

      {missingFields && (
        <div className="mb-7 text-[13px] text-warn bg-warn/8 border border-warn/25 rounded-2xl px-4 py-3 flex items-start gap-3">
          <span className="mt-0.5 w-1.5 h-1.5 rounded-full bg-warn flex-shrink-0" />
          <p className="leading-relaxed">
            <b className="text-ink">Some fields are empty.</b> This site is
            JS-heavy or doesn't surface contact / hours info. Fill them in below
            so the agent has the full picture.
          </p>
        </div>
      )}

      {/* ─── Section 1 · Identity ─────────────────────────────── */}
      <Section title="Identity" subtitle="What the business is called and what they do">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          <Field label="Business name" value={value("name")} onChange={(v) => update("name", v)} />
          <Field label="Type" value={value("type")} onChange={(v) => update("type", v)} />
          <Field
            label="Tagline"
            value={brandValue("tagline")}
            onChange={(v) => update("brand.tagline", v)}
          />
          <Field label="Tone" value={brandValue("tone")} onChange={(v) => update("brand.tone", v)} />
        </div>
        <div className="mt-5">
          <Field
            label="Description"
            value={value("description")}
            onChange={(v) => update("description", v)}
            textarea
          />
        </div>
      </Section>

      {/* ─── Section 2 · Contact ──────────────────────────────── */}
      <Section title="Contact" subtitle="Where customers reach the business">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          <Field label="City" value={value("city")} onChange={(v) => update("city", v)} />
          <Field
            label="Contact phone"
            value={value("contact_phone")}
            onChange={(v) => update("contact_phone", v)}
          />
          <Field label="Email" value={value("email")} onChange={(v) => update("email", v)} />
          <Field label="Hours" value={value("timings")} onChange={(v) => update("timings", v)} />
        </div>
      </Section>

      {/* ─── Section 3 · Services ─────────────────────────────── */}
      <Section title="Services" subtitle="What the agent will mention in posts and replies">
        <Field
          label="Services (comma-separated)"
          value={edits.services ?? profile.services.join(", ")}
          onChange={(v) => update("services", v)}
          textarea
        />
      </Section>

      {/* ─── Section 4 · Brand ────────────────────────────────── */}
      <Section
        title="Brand kit"
        subtitle="Colors + logo the agent will use on every visual it produces"
      >
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4 mb-6">
          <ColorField
            label="Primary"
            value={brandValue("primary_color")}
            onChange={(v) => update("brand.primary_color", v)}
          />
          <ColorField
            label="Secondary"
            value={brandValue("secondary_color")}
            onChange={(v) => update("brand.secondary_color", v)}
          />
          <ColorField
            label="Accent"
            value={brandValue("accent_color")}
            onChange={(v) => update("brand.accent_color", v)}
          />
        </div>

        {profile.logo_url ? (
          <div>
            <p className="font-mono text-[10px] text-text-mute uppercase tracking-[0.18em] mb-2">
              Detected logo
            </p>
            <div className="flex items-start gap-4 p-4 bg-bg border border-border rounded-2xl">
              <div className="w-24 h-24 bg-white rounded-xl border border-border flex items-center justify-center flex-shrink-0 overflow-hidden">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={profile.logo_url}
                  alt="Logo"
                  className="max-w-full max-h-full object-contain"
                  referrerPolicy="no-referrer"
                  onError={(e) => {
                    const t = e.currentTarget;
                    if (!t.src.includes("/api/img?")) {
                      t.src = `/api/img?url=${encodeURIComponent(
                        profile.logo_url!,
                      )}`;
                    } else {
                      t.style.display = "none";
                    }
                  }}
                />
              </div>
              <div className="flex-1 min-w-0 pt-1">
                <p className="text-[13px] text-text-dim mb-1.5">
                  Composited onto every poster + image the agent generates.
                </p>
                <p className="font-mono text-[10px] text-text-mute break-all leading-relaxed">
                  {profile.logo_url}
                </p>
              </div>
            </div>
          </div>
        ) : (
          <div className="text-[12px] text-text-mute bg-bg border border-border rounded-2xl px-4 py-3">
            No logo detected. Posters will use a typographic wordmark
            ({profile.name || "your business name"}) as the brand badge.
          </div>
        )}
      </Section>

      {/* ─── Actions ──────────────────────────────────────────── */}
      <div className="mt-2 pt-6 border-t border-border flex flex-col-reverse sm:flex-row gap-3 sm:justify-end sm:items-center">
        <button
          onClick={() => router.push("/onboarding/business")}
          className="px-5 py-2.5 rounded-full border border-border text-text-dim hover:text-ink hover:border-border-strong transition text-[13px]"
        >
          Try another link
        </button>
        <button
          onClick={submit}
          disabled={busy}
          className="btn-primary flex items-center gap-2 disabled:opacity-50"
        >
          {busy ? (
            <Loader2 size={16} className="animate-spin" />
          ) : (
            <ArrowRight size={16} />
          )}
          Confirm and continue
        </button>
      </div>

      {err && (
        <div className="mt-3 text-xs text-danger bg-danger/10 border border-danger/20 rounded-xl p-3" role="alert">
          <p className="font-medium mb-1">Could not save profile</p>
          <p className="font-mono text-[11px] break-all opacity-80">{err}</p>
        </div>
      )}
    </div>
  );
}

/**
 * Visual section break. Each block of the wizard becomes a labelled
 * group — better hierarchy than fields-jammed-together.
 */
function Section({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="py-6 border-t border-border first:border-t-0 first:pt-0">
      <div className="mb-4">
        <h2 className="font-display italic text-[20px] text-ink tracking-editorial leading-none mb-1.5">
          {title}
        </h2>
        {subtitle && (
          <p className="text-[12px] text-text-mute leading-relaxed">{subtitle}</p>
        )}
      </div>
      {children}
    </section>
  );
}

function Field({
  label,
  value,
  onChange,
  textarea,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  textarea?: boolean;
}) {
  const isEmpty = !value || !value.trim();
  const Comp = textarea ? "textarea" : "input";
  return (
    <label className="block">
      <span className="font-mono text-[10px] text-text-mute uppercase tracking-[0.18em] font-medium block mb-1.5">
        {label}
        {isEmpty && (
          <span className="ml-2 text-warn normal-case tracking-normal font-sans">
            · empty
          </span>
        )}
      </span>
      <Comp
        value={value || ""}
        onChange={(e) => onChange(e.target.value)}
        rows={textarea ? 3 : undefined}
        placeholder={isEmpty ? "Fill manually" : undefined}
        className="w-full bg-bg border border-border rounded-xl px-3.5 py-2.5 text-[14px] text-ink outline-none focus:border-ink/40 transition placeholder:text-text-mute"
      />
    </label>
  );
}

function ColorField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  const isEmpty = !value || !value.trim();
  // Detect near-white (or weirdly-pale) swatches so we can outline them
  // strongly — otherwise they disappear against the white card.
  const isPale = !isEmpty && _isPaleHex(value);
  return (
    <label className="block">
      <span className="font-mono text-[10px] text-text-mute uppercase tracking-[0.18em] font-medium block mb-2">
        {label}
      </span>
      <div className="bg-bg border border-border rounded-2xl overflow-hidden">
        <div
          className={`h-20 flex items-center justify-center ${
            isEmpty
              ? "bg-bg border-b border-dashed border-border-strong/40"
              : isPale
                ? "border-b-2 border-border-strong"
                : "border-b border-border"
          }`}
          style={{ backgroundColor: isEmpty ? undefined : value }}
          aria-label={isEmpty ? "No color set" : value}
        >
          {isEmpty && (
            <span className="font-mono text-[10px] text-text-mute uppercase tracking-wider">
              not set
            </span>
          )}
        </div>
        <input
          value={value || ""}
          onChange={(e) => onChange(e.target.value)}
          placeholder="#hex"
          className="w-full bg-transparent border-0 px-3 py-2.5 text-[13px] text-ink outline-none focus:bg-ink/[0.02] transition font-mono placeholder:text-text-mute"
        />
      </div>
    </label>
  );
}

function _isPaleHex(hex: string): boolean {
  // Treat anything with avg channel > 230 as "pale" so we add visible
  // outline — otherwise a near-white swatch on a white card vanishes.
  if (!hex.startsWith("#") || (hex.length !== 4 && hex.length !== 7)) {
    return false;
  }
  let h = hex.slice(1);
  if (h.length === 3) h = h.split("").map((c) => c + c).join("");
  try {
    const r = parseInt(h.slice(0, 2), 16);
    const g = parseInt(h.slice(2, 4), 16);
    const b = parseInt(h.slice(4, 6), 16);
    return (r + g + b) / 3 > 230;
  } catch {
    return false;
  }
}
