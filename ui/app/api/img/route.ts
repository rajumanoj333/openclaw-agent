/**
 * Same-origin image proxy.
 *
 * <img> tags can't send custom headers, so browsers loading our ngrok-hosted
 * media URLs hit the ngrok interstitial and fail. We proxy through this
 * route, attach the bypass header + browser UA server-side, and stream
 * bytes back as a same-origin response.
 *
 * Used as the FALLBACK when a direct <img src> fails for external logos —
 * see ui/app/onboarding/confirm/page.tsx onError handler.
 */
import { NextRequest } from "next/server";

export const runtime = "edge";

// Allowlist behavior:
//   - Dev: allow any HTTPS host so arbitrary customer logos load.
//   - Prod: restrict to known hosts (anti-SSRF / anti-open-redirect).
const DEV_ALLOW_ANY_HTTPS = process.env.NODE_ENV !== "production";

const ALLOWED_HOSTS = [
  /\.ngrok-free\.(dev|app)$/,
  /\.cloudapp\.azure\.com$/,
  /\.sslip\.io$/,
  /^localhost(:\d+)?$/,
  /^127\.0\.0\.1(:\d+)?$/,
];

function hostAllowed(host: string, scheme: string): boolean {
  if (DEV_ALLOW_ANY_HTTPS && scheme === "https:") return true;
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
  if (!hostAllowed(parsed.host, parsed.protocol)) {
    return new Response("host not allowed", { status: 403 });
  }

  const upstream = await fetch(target, {
    headers: {
      "ngrok-skip-browser-warning": "1",
      // Browser UA — many CDNs (Apple, Cloudflare-protected sites) block
      // the default fetch UA + return 403 / serve HTML interstitial.
      "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
      Accept: "image/avif,image/webp,image/png,image/svg+xml,image/*,*/*;q=0.8",
    },
    cache: "no-store",
  });

  if (!upstream.ok) {
    return new Response(`upstream ${upstream.status}`, { status: 502 });
  }

  const ct = upstream.headers.get("content-type") || "application/octet-stream";
  return new Response(upstream.body, {
    status: 200,
    headers: {
      "content-type": ct,
      "cache-control": "public, max-age=600",
    },
  });
}
