/**
 * Cloudflare Pages Function — 같은 도메인에서 도는 CORS 프록시
 * 남의 공개 프록시(allorigins/corsproxy)가 죽거나 pages.dev를 차단하는 문제 해결.
 * 호출: /api/proxy?url=<인코딩된 대상 URL>
 * 허용된 시세 API 호스트만 통과 (오픈 프록시 악용 방지)
 */
const ALLOWED = new Set([
  "query1.finance.yahoo.com",
  "query2.finance.yahoo.com",
  "api.upbit.com",
  "api.binance.com",
  "fapi.binance.com",
  "api.bybit.com",
  "open.er-api.com",
  "cdn.jsdelivr.net",
  "quotation-api-cdn.dunamu.com"
]);

export async function onRequest(context) {
  const { request } = context;
  const cors = {
    "access-control-allow-origin": "*",
    "access-control-allow-methods": "GET, OPTIONS",
    "access-control-allow-headers": "*"
  };
  if (request.method === "OPTIONS") return new Response(null, { headers: cors });

  const target = new URL(request.url).searchParams.get("url");
  if (!target) return new Response("missing url param", { status: 400, headers: cors });

  let t;
  try { t = new URL(target); } catch { return new Response("bad url", { status: 400, headers: cors }); }
  if (t.protocol !== "https:" || !ALLOWED.has(t.hostname)) {
    return new Response("host not allowed", { status: 403, headers: cors });
  }

  try {
    const upstream = await fetch(t.toString(), {
      headers: { "User-Agent": "Mozilla/5.0", "Accept": "application/json,text/plain,*/*" },
      cf: { cacheTtl: 10, cacheEverything: true }
    });
    const body = await upstream.arrayBuffer();
    return new Response(body, {
      status: upstream.status,
      headers: {
        ...cors,
        "content-type": upstream.headers.get("content-type") || "application/json",
        "cache-control": "public, max-age=10"
      }
    });
  } catch (e) {
    return new Response(JSON.stringify({ error: String(e) }), { status: 502, headers: { ...cors, "content-type": "application/json" } });
  }
}
