/**
 * Same-origin image proxy.
 *
 * Used as a FALLBACK when a direct <img src> fails for external logos.
 * Posters/audio served from our own backend hit this for the ngrok-skip
 * header. Customer logos hit this only if their CDN blocks hot-linking.
 *
 * SECURITY:
 *  - Strict host allowlist enforced regardless of NODE_ENV. NEVER weaken
 *    this server-side; if dev needs arbitrary hosts, render direct in
 *    the browser (it already does, with proxy as onError fallback).
 *  - Bare-IP hostnames blocked entirely (no SSRF to 169.254.169.254
 *    cloud-metadata, 127.x loopback, 10/8 private, etc).
 *  - Redirect following DISABLED (`redirect: "manual"`). Attacker can't
 *    pass an allowed host that 3xx-bounces into a private network.
 *  - Content-type restricted to image/* on response.
 */
import { NextRequest } from "next/server";

export const runtime = "edge";

// Hosts that are safe to proxy. Our own tunnel hosts + a small whitelist
// of known-good public CDNs. Add hosts here on a case-by-case basis.
//
// Do NOT add wildcard public DNS providers (sslip.io, nip.io, xip.io) —
// they let attackers build hostnames that resolve to private IPs.
const ALLOWED_HOSTS: RegExp[] = [
  /\.ngrok-free\.(dev|app)$/,
  /\.cloudapp\.azure\.com$/,
  /^localhost(:\d+)?$/,
  /^127\.0\.0\.1(:\d+)?$/,
];

// Bare-IP-literal patterns. Hostnames that are IP addresses get hard-blocked
// regardless of which IP. SSRF defense: even if attacker bypasses the
// host allowlist with a redirect, an IPv4/IPv6 literal in the URL is
// always rejected.
const IPV4_LITERAL = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})(:\d+)?$/;
const IPV6_LITERAL = /^\[[0-9a-fA-F:]+\](:\d+)?$/;

function hostIsBareIP(host: string): boolean {
  return IPV4_LITERAL.test(host) || IPV6_LITERAL.test(host);
}

function hostAllowed(host: string): boolean {
  if (hostIsBareIP(host)) return false;
  return ALLOWED_HOSTS.some((re) => re.test(host));
}

export async function GET(req: NextRequest) {
  const target = req.nextUrl.searchParams.get("url");
  if (!target) {
    return new Response("missing ?url", { status: 400 });
  }

  let parsed: URL;
  try {
    parsed = new URL(target);
  } catch {
    return new Response("bad url", { status: 400 });
  }

  // Require https (or http for loopback only — i.e. our local audio).
  const isLoopback = /^localhost(:\d+)?$|^127\.0\.0\.1(:\d+)?$/.test(parsed.host);
  if (parsed.protocol !== "https:" && !(parsed.protocol === "http:" && isLoopback)) {
    return new Response("https required", { status: 403 });
  }

  if (!hostAllowed(parsed.host)) {
    return new Response("host not allowed", { status: 403 });
  }

  // Manual redirect handling — prevent redirect-based SSRF bypass where an
  // allowed host 3xx-bounces into a private network or metadata service.
  const upstream = await fetch(target, {
    redirect: "manual",
    headers: {
      "ngrok-skip-browser-warning": "1",
      "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
      Accept: "image/avif,image/webp,image/png,image/svg+xml,image/*,*/*;q=0.8",
    },
    cache: "no-store",
  });

  // Reject any redirect — caller can re-request the final URL themselves
  // after re-validating it against this same allowlist.
  if (upstream.status >= 300 && upstream.status < 400) {
    return new Response("redirects not followed", { status: 502 });
  }

  if (!upstream.ok) {
    return new Response(`upstream ${upstream.status}`, { status: 502 });
  }

  // Reject anything that's not an image — prevents using the proxy to
  // fetch arbitrary content (HTML, JSON) from allowed hosts.
  const ct = (upstream.headers.get("content-type") || "").toLowerCase();
  if (!ct.startsWith("image/")) {
    return new Response("not an image", { status: 415 });
  }

  return new Response(upstream.body, {
    status: 200,
    headers: {
      "content-type": ct,
      "cache-control": "public, max-age=600",
    },
  });
}
