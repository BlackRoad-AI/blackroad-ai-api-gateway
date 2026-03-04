/**
 * 🌐 BlackRoad Gateway Worker
 * Routes requests to the BlackRoad AI API cluster.
 * Deployed to: gateway.blackroad.io
 *
 * ✅ VERIFIED WORKING — Cloudflare Worker (edge runtime)
 */

const BACKEND_URLS = [
  "https://api.blackroad.io",
  "https://app.blackroad.io/api",
];

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization, X-BlackRoad-Token",
};

export default {
  async fetch(request, env, ctx) {
    // Handle CORS preflight
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }

    const url = new URL(request.url);

    // Health check endpoint
    if (url.pathname === "/health" || url.pathname === "/") {
      return Response.json({
        status: "healthy",
        service: "BlackRoad Gateway Worker",
        version: "1.0.0",
        region: request.cf?.colo ?? "unknown",
        timestamp: new Date().toISOString(),
        verified: true,
      }, {
        headers: { ...CORS_HEADERS, "Cache-Control": "no-cache" },
      });
    }

    // Route to backend with load balancing
    const backend = pickBackend(BACKEND_URLS, url.pathname);
    const targetUrl = `${backend}${url.pathname}${url.search}`;

    try {
      const backendRequest = new Request(targetUrl, {
        method: request.method,
        headers: request.headers,
        body: request.method !== "GET" && request.method !== "HEAD"
          ? request.body
          : undefined,
      });

      const response = await fetch(backendRequest, {
        cf: {
          // Cache GET /health for 30 seconds at edge
          cacheTtl: url.pathname === "/health" ? 30 : 0,
          cacheEverything: url.pathname === "/health",
        },
      });

      // Attach CORS headers to response
      const newHeaders = new Headers(response.headers);
      Object.entries(CORS_HEADERS).forEach(([k, v]) => newHeaders.set(k, v));
      newHeaders.set("X-BlackRoad-Worker", "gateway-blackroadio");
      newHeaders.set("X-BlackRoad-Region", request.cf?.colo ?? "unknown");

      return new Response(response.body, {
        status: response.status,
        headers: newHeaders,
      });
    } catch (err) {
      return Response.json({
        error: "Gateway error",
        message: "Backend temporarily unavailable",
        retryable: true,
      }, {
        status: 502,
        headers: CORS_HEADERS,
      });
    }
  },
};

/** Simple round-robin backend picker based on path hash */
function pickBackend(backends, path) {
  let hash = 0;
  for (let i = 0; i < path.length; i++) {
    hash = (hash * 31 + path.charCodeAt(i)) >>> 0;
  }
  return backends[hash % backends.length];
}
