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

  return (
    <div className="card p-8 fade-in">
      <StepIndicator active={1} />

      <h1 className="font-display italic text-[30px] leading-none tracking-editorial text-ink mb-3">
        Does this look right?
      </h1>
      <p className="text-sm text-text-dim mb-6 leading-relaxed">
        Edit anything that's wrong. The agent will use exactly these details.
      </p>

      {(!profile.name ||
        !profile.description ||
        profile.services.length === 0) && (
        <div className="text-xs text-warn bg-warn/10 border border-warn/30 rounded-xl p-3 mb-5">
          Some fields couldn't be auto-extracted (this site is JS-heavy or
          sparse on text). Please fill in the missing details below.
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Field label="Business name" value={value("name")} onChange={(v) => update("name", v)} />
        <Field label="Type" value={value("type")} onChange={(v) => update("type", v)} />
        <Field
          label="Tagline"
          value={brandValue("tagline")}
          onChange={(v) => update("brand.tagline", v)}
        />
        <Field label="City" value={value("city")} onChange={(v) => update("city", v)} />
        <Field
          label="Contact phone"
          value={value("contact_phone")}
          onChange={(v) => update("contact_phone", v)}
        />
        <Field label="Email" value={value("email")} onChange={(v) => update("email", v)} />
        <Field label="Timings" value={value("timings")} onChange={(v) => update("timings", v)} />
        <Field label="Tone" value={brandValue("tone")} onChange={(v) => update("brand.tone", v)} />
      </div>

      <div className="mt-4">
        <Field
          label="Description"
          value={value("description")}
          onChange={(v) => update("description", v)}
          textarea
        />
      </div>

      <div className="mt-4">
        <Field
          label="Services (comma-separated)"
          value={edits.services ?? profile.services.join(", ")}
          onChange={(v) => update("services", v)}
          textarea
        />
      </div>

      <div className="mt-5">
        <h3 className="text-xs font-medium text-text-dim uppercase tracking-wider mb-2">
          Brand colors
        </h3>
        <div className="grid grid-cols-3 gap-3">
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
      </div>

      {profile.logo_url && (
        <div className="mt-5">
          <h3 className="text-xs font-medium text-text-dim uppercase tracking-wider mb-2">
            Detected logo
          </h3>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={`/api/img?url=${encodeURIComponent(profile.logo_url)}`}
            alt="Logo"
            className="max-h-24 rounded-xl border border-border bg-white p-2"
            referrerPolicy="no-referrer"
          />
        </div>
      )}

      <div className="mt-7 pt-5 border-t border-border flex gap-2 justify-end">
        <button
          onClick={() => router.push("/onboarding/business")}
          className="px-4 py-2 rounded-full border border-border text-text-dim hover:text-text hover:border-border-strong transition text-sm"
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
        <p className="mt-3 text-xs text-danger bg-danger/10 border border-danger/20 rounded-xl p-3 break-all">
          {err}
        </p>
      )}
    </div>
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
  const Comp = textarea ? "textarea" : "input";
  return (
    <label className="block">
      <span className="text-[11px] text-text-mute uppercase tracking-wider font-medium block mb-1.5">
        {label}
      </span>
      <Comp
        value={value || ""}
        onChange={(e) => onChange(e.target.value)}
        rows={textarea ? 3 : undefined}
        className="w-full bg-bg border border-border rounded-xl px-3 py-2 text-sm text-text outline-none focus:border-text/40 transition placeholder:text-text-mute"
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
  return (
    <label className="block">
      <span className="text-[11px] text-text-mute uppercase tracking-wider font-medium block mb-1.5">
        {label}
      </span>
      <div className="flex items-center gap-2">
        <span
          className="w-9 h-9 rounded-lg border border-border flex-shrink-0"
          style={{ backgroundColor: value || "transparent" }}
        />
        <input
          value={value || ""}
          onChange={(e) => onChange(e.target.value)}
          placeholder="#hex"
          className="flex-1 bg-bg border border-border rounded-xl px-3 py-2 text-sm text-text outline-none focus:border-text/40 transition font-mono placeholder:text-text-mute"
        />
      </div>
    </label>
  );
}
