/**
 * Same-origin image proxy.
 *
 * <img> tags can't send custom headers, so browsers loading our ngrok-hosted
 * media URLs hit the ngrok interstitial and fail. We proxy through this
 * route, attach the bypass header server-side, and stream bytes back as a
 * same-origin response that browsers render directly.
 */
import { NextRequest } from "next/server";

export const runtime = "edge";

const ALLOWED_HOSTS = [
  /\.ngrok-free\.(dev|app)$/,
  /\.cloudapp\.azure\.com$/,
  /^localhost(:\d+)?$/,
  /^127\.0\.0\.1(:\d+)?$/,
];

function hostAllowed(host: string): boolean {
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
  if (!hostAllowed(parsed.host)) {
    return new Response("host not allowed", { status: 403 });
  }

  const upstream = await fetch(target, {
    headers: { "ngrok-skip-browser-warning": "1" },
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
