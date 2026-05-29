"use client";

import { Calendar, Copy, Hash, Receipt, TrendingUp } from "lucide-react";
import { useState } from "react";

/**
 * Structured-output rendering for agent replies.
 *
 * Each agent (Ritu/Kiran/Anika/Morpheus) emits replies in two parts:
 *   1) one short intro sentence (plain text)
 *   2) an XML-tagged JSON block — POST_PREVIEW, INVOICE_DRAFT, etc.
 *
 * The parser extracts both. message-bubble renders the intro as text +
 * each block as a styled card. Unknown blocks fall through to <pre>.
 */

const BLOCK_RE =
  /<(POST_PREVIEW|INVOICE_DRAFT|OFFER_POST_CARD|COMPETITOR_VIEW)>([\s\S]*?)<\/\1>/g;

interface ParsedBlock {
  name: string;
  data: any;
  raw: string;
}

export interface ParsedReply {
  intro: string;
  blocks: ParsedBlock[];
}

export function parseStructuredReply(text: string): ParsedReply {
  if (!text) return { intro: "", blocks: [] };
  const blocks: ParsedBlock[] = [];
  const matches = Array.from(text.matchAll(BLOCK_RE));
  for (const m of matches) {
    const [full, name, body] = m;
    try {
      const data = JSON.parse(body.trim());
      blocks.push({ name, data, raw: full });
    } catch {
      // unparseable JSON inside a tagged block — keep raw so the user sees it
      blocks.push({ name, data: null, raw: full });
    }
  }
  let intro = text;
  for (const b of blocks) {
    intro = intro.replace(b.raw, "").trim();
  }
  return { intro, blocks };
}

/** Top-level dispatcher: render the right card per block.name. */
export function StructuredBlock({ block }: { block: ParsedBlock }) {
  if (!block.data) {
    return (
      <div className="mt-3 rounded-2xl border border-warn/30 bg-warn/5 p-3 font-mono text-[11px] text-text-dim">
        <p className="font-medium text-warn mb-1">{block.name} — malformed JSON</p>
        <pre className="whitespace-pre-wrap break-all opacity-80">{block.raw}</pre>
      </div>
    );
  }
  switch (block.name) {
    case "POST_PREVIEW":
      return <PostPreviewCard data={block.data} />;
    case "OFFER_POST_CARD":
      return <OfferPostCardCard data={block.data} />;
    case "INVOICE_DRAFT":
      return <InvoiceDraftCard data={block.data} />;
    case "COMPETITOR_VIEW":
      return <CompetitorViewCard data={block.data} />;
    default:
      return null;
  }
}

// ─── Cards ─────────────────────────────────────────────────────────────

function copyButton(text: string) {
  return <CopyChip text={text} />;
}

function CopyChip({ text }: { text: string }) {
  const [done, setDone] = useState(false);
  const onClick = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setDone(true);
      setTimeout(() => setDone(false), 1400);
    } catch {
      /* ignore */
    }
  };
  return (
    <button
      onClick={onClick}
      className="inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-wider border border-ink/15 hover:border-ink/40 hover:bg-ink/5 rounded-full px-2 py-0.5 transition"
      style={{ color: "hsl(220 30% 8%)" }}
      aria-label="Copy"
    >
      <Copy size={11} />
      {done ? "copied" : "copy"}
    </button>
  );
}

function PostPreviewCard({ data }: { data: any }) {
  const caption: string = data.caption || "";
  const hashtags: string[] = Array.isArray(data.hashtags) ? data.hashtags : [];
  const platforms: string[] = Array.isArray(data.platforms) ? data.platforms : [];
  const time: string = data.suggested_time || "";
  return (
    <div className="mt-3 rounded-2xl border border-whatsapp/30 bg-whatsapp/5 p-4">
      <div className="flex items-center justify-between gap-2 mb-2">
        <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-whatsapp font-semibold">
          Post preview · Ritu
        </span>
        {copyButton(
          [caption, hashtags.join(" ")].filter(Boolean).join("\n\n"),
        )}
      </div>
      <p className="text-[14px] text-ink leading-relaxed whitespace-pre-wrap mb-3">
        {caption}
      </p>
      {hashtags.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-3">
          {hashtags.map((h) => (
            <span
              key={h}
              className="font-mono text-[11px] text-text-dim bg-bg border border-border rounded-full px-2 py-0.5 inline-flex items-center gap-1"
            >
              <Hash size={10} />
              {h.replace(/^#/, "")}
            </span>
          ))}
        </div>
      )}
      <div className="flex items-center gap-3 text-[11px] text-text-mute font-mono uppercase tracking-wider">
        {platforms.length > 0 && (
          <span>→ {platforms.join(", ").toLowerCase()}</span>
        )}
        {time && (
          <span className="inline-flex items-center gap-1">
            <Calendar size={11} /> {time}
          </span>
        )}
      </div>
    </div>
  );
}

function OfferPostCardCard({ data }: { data: any }) {
  const name: string = data.offer_name || "Offer";
  const validTill: string = data.valid_till || "";
  const igCap: string = data.instagram_caption || "";
  const waMsg: string = data.whatsapp_message || "";
  const story: string = data.story_text || "";
  const hashtags: string[] = Array.isArray(data.hashtags) ? data.hashtags : [];
  const tips: string[] = Array.isArray(data.posting_tips) ? data.posting_tips : [];
  return (
    <div className="mt-3 rounded-2xl border border-accent/30 bg-accent/5 p-4">
      <div className="flex items-center justify-between gap-2 mb-2">
        <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-accent font-semibold">
          Offer · Ritu
        </span>
        {validTill && (
          <span className="font-mono text-[10px] text-text-mute uppercase">
            valid till {validTill}
          </span>
        )}
      </div>
      <h4 className="font-display italic text-[20px] text-ink mb-3">{name}</h4>

      <OfferSection label="Instagram caption" body={igCap} />
      <OfferSection label="WhatsApp message" body={waMsg} />
      <OfferSection label="Story text" body={story} />

      {hashtags.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mt-2 mb-2">
          {hashtags.map((h) => (
            <span
              key={h}
              className="font-mono text-[11px] text-text-dim bg-bg border border-border rounded-full px-2 py-0.5"
            >
              {h}
            </span>
          ))}
        </div>
      )}

      {tips.length > 0 && (
        <div className="mt-3 pt-3 border-t border-border/60">
          <p className="font-mono text-[10px] uppercase tracking-wider text-text-mute mb-1.5">
            Posting tips
          </p>
          <ul className="space-y-1 text-[13px] text-text-dim">
            {tips.map((t, i) => (
              <li key={i} className="leading-relaxed">
                · {t}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function OfferSection({ label, body }: { label: string; body: string }) {
  if (!body) return null;
  return (
    <div className="mb-3">
      <div className="flex items-center justify-between mb-1">
        <p className="font-mono text-[10px] uppercase tracking-wider text-text-mute">
          {label}
        </p>
        {copyButton(body)}
      </div>
      <p className="text-[13px] text-ink leading-relaxed whitespace-pre-wrap">
        {body}
      </p>
    </div>
  );
}

function InvoiceDraftCard({ data }: { data: any }) {
  const customer: string = data.customer_name || "";
  const items: Array<any> = Array.isArray(data.items) ? data.items : [];
  const subtotal: number = Number(data.subtotal) || 0;
  const taxLabel: string = data.tax_label || "Tax";
  const taxAmount: number = Number(data.tax_amount) || 0;
  const grand: number = Number(data.grand_total) || subtotal + taxAmount;
  const due: string = data.due_date || "";
  const payNote: string = data.payment_note || "";

  return (
    <div className="mt-3 rounded-2xl border border-voice/30 bg-voice/5 p-4">
      <div className="flex items-center justify-between gap-2 mb-2">
        <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-voice font-semibold">
          <Receipt size={11} className="inline-block mr-1" />
          Invoice draft · Kiran
        </span>
        {due && (
          <span className="font-mono text-[10px] text-text-mute uppercase">
            due {due}
          </span>
        )}
      </div>

      {customer && (
        <p className="text-[14px] text-ink mb-2">
          <span className="text-text-mute">To: </span>
          <span className="font-medium">{customer}</span>
        </p>
      )}

      {items.length > 0 && (
        <table className="w-full text-[13px] mb-3">
          <thead>
            <tr className="text-left text-text-mute font-mono text-[10px] uppercase tracking-wider border-b border-border">
              <th className="py-1 pr-2">Item</th>
              <th className="py-1 px-2 text-right w-12">Qty</th>
              <th className="py-1 px-2 text-right w-20">Rate</th>
              <th className="py-1 pl-2 text-right w-24">Total</th>
            </tr>
          </thead>
          <tbody className="text-text-dim">
            {items.map((it, i) => (
              <tr key={i} className="border-b border-border/40 last:border-0">
                <td className="py-1.5 pr-2 align-top">{it.description}</td>
                <td className="py-1.5 px-2 text-right tabular-nums">{it.qty}</td>
                <td className="py-1.5 px-2 text-right tabular-nums">
                  {fmtCurrency(it.rate)}
                </td>
                <td className="py-1.5 pl-2 text-right tabular-nums">
                  {fmtCurrency(it.total)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div className="space-y-0.5 text-[13px] text-text-dim font-mono tabular-nums">
        <Row label="Subtotal" value={fmtCurrency(subtotal)} />
        <Row label={taxLabel} value={fmtCurrency(taxAmount)} />
        <Row label="Total" value={fmtCurrency(grand)} bold />
      </div>

      {payNote && (
        <p className="text-[12px] text-text-mute mt-3 leading-relaxed">
          Payment: {payNote}
        </p>
      )}
    </div>
  );
}

function Row({
  label,
  value,
  bold,
}: {
  label: string;
  value: string;
  bold?: boolean;
}) {
  return (
    <div
      className={`flex items-center justify-between ${
        bold ? "text-ink font-semibold pt-1 mt-1 border-t border-border" : ""
      }`}
    >
      <span>{label}</span>
      <span>{value}</span>
    </div>
  );
}

function fmtCurrency(n: number | string): string {
  const v = typeof n === "number" ? n : Number(n) || 0;
  return `₹ ${v.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

function CompetitorViewCard({ data }: { data: any }) {
  return (
    <div className="mt-3 rounded-2xl border border-warn/30 bg-warn/5 p-4">
      <div className="flex items-center justify-between gap-2 mb-3">
        <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-warn font-semibold">
          <TrendingUp size={11} className="inline-block mr-1" />
          Competitor view · Anika
        </span>
        <span className="font-display italic text-[16px] text-ink">
          vs {data.competitor || "competitor"}
        </span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
        <KvBlock label="Their advantage" body={data.their_advantage} />
        <KvBlock label="Your advantage" body={data.your_advantage} />
      </div>
      <KvBlock label="Open gap" body={data.open_gap} />
      <div className="mt-3 pt-3 border-t border-border/60">
        <p className="font-mono text-[10px] uppercase tracking-wider text-text-mute mb-1">
          Next move (this week)
        </p>
        <p className="text-[14px] text-ink leading-relaxed">{data.next_move}</p>
      </div>
    </div>
  );
}

function KvBlock({ label, body }: { label: string; body: string }) {
  if (!body) return null;
  return (
    <div>
      <p className="font-mono text-[10px] uppercase tracking-wider text-text-mute mb-1">
        {label}
      </p>
      <p className="text-[13px] text-text-dim leading-relaxed">{body}</p>
    </div>
  );
}
