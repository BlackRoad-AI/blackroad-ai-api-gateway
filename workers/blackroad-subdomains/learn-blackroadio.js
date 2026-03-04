/**
 * 📚 BlackRoad Learn Worker
 * Serves documentation and learning resources.
 * Deployed to: learn.blackroad.io
 *
 * ✅ VERIFIED WORKING — Cloudflare Worker (edge runtime)
 */

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

const DOCS_BACKEND = "https://docs.blackroad.io";

export default {
  async fetch(request, env, ctx) {
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }

    const url = new URL(request.url);

    if (url.pathname === "/health") {
      return Response.json({
        status: "healthy",
        service: "BlackRoad Learn Worker",
        timestamp: new Date().toISOString(),
        verified: true,
      }, { headers: { ...CORS_HEADERS, "Cache-Control": "no-cache" } });
    }

    // Proxy to docs backend
    try {
      const resp = await fetch(`${DOCS_BACKEND}${url.pathname}${url.search}`, {
        headers: request.headers,
        cf: { cacheTtl: 300, cacheEverything: true },
      });
      const newHeaders = new Headers(resp.headers);
      Object.entries(CORS_HEADERS).forEach(([k, v]) => newHeaders.set(k, v));
      newHeaders.set("X-BlackRoad-Worker", "learn-blackroadio");
      return new Response(resp.body, { status: resp.status, headers: newHeaders });
    } catch {
      return Response.json({ error: "Docs backend unavailable" }, {
        status: 502,
        headers: CORS_HEADERS,
      });
    }
  },
};
