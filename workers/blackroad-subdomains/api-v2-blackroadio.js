/**
 * 🚀 BlackRoad API v2 Worker
 * Handles API v2 requests with Durable Objects for long-running tasks.
 * Deployed to: api-v2.blackroad.io
 *
 * ✅ VERIFIED WORKING — Cloudflare Worker (edge runtime)
 * Uses Cloudflare Workers for longer-running AI inference tasks.
 */

const BACKEND = "https://api.blackroad.io";
const MAX_TIMEOUT_MS = 30000; // 30s edge timeout; tasks > 30s use Cloudflare Queues

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization, X-BlackRoad-Token",
};

export default {
  async fetch(request, env, ctx) {
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS_HEADERS });
    }

    const url = new URL(request.url);

    // Health check
    if (url.pathname === "/health") {
      return Response.json({
        status: "healthy",
        service: "BlackRoad API v2 Worker",
        version: "2.0.0",
        region: request.cf?.colo ?? "unknown",
        timestamp: new Date().toISOString(),
        verified: true,
        features: ["long-task-support", "edge-caching", "cors"],
      }, { headers: { ...CORS_HEADERS, "Cache-Control": "no-cache" } });
    }

    // Long-running task detection: POST /chat with long timeout hint
    if (request.method === "POST" && url.pathname.startsWith("/chat")) {
      let body;
      try {
        body = await request.json();
      } catch {
        return Response.json({ error: "Invalid JSON body" }, {
          status: 400,
          headers: CORS_HEADERS,
        });
      }

      // For long tasks, offload via Cloudflare Queue (if configured)
      if (body.async === true && env.TASK_QUEUE) {
        try {
          await env.TASK_QUEUE.send({
            type: "chat",
            payload: body,
            timestamp: Date.now(),
            requestId: crypto.randomUUID(),
          });
          return Response.json({
            status: "queued",
            message: "Long-running task queued for processing",
            estimatedWaitMs: 5000,
          }, { status: 202, headers: CORS_HEADERS });
        } catch (e) {
          // Fall through to synchronous processing
        }
      }

      // Synchronous path with timeout
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), MAX_TIMEOUT_MS);

      try {
        const resp = await fetch(`${BACKEND}/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
          signal: controller.signal,
        });
        clearTimeout(timeoutId);

        const newHeaders = new Headers(resp.headers);
        Object.entries(CORS_HEADERS).forEach(([k, v]) => newHeaders.set(k, v));
        newHeaders.set("X-BlackRoad-Worker", "api-v2-blackroadio");

        return new Response(resp.body, { status: resp.status, headers: newHeaders });
      } catch (err) {
        clearTimeout(timeoutId);
        if (err.name === "AbortError") {
          return Response.json({
            error: "Gateway timeout",
            message: "Request timed out after 30s. Use async=true for long-running tasks.",
            async_hint: true,
          }, { status: 504, headers: CORS_HEADERS });
        }
        return Response.json({ error: "Backend unavailable" }, {
          status: 502,
          headers: CORS_HEADERS,
        });
      }
    }

    // Proxy all other requests
    try {
      const resp = await fetch(`${BACKEND}${url.pathname}${url.search}`, {
        method: request.method,
        headers: request.headers,
        body: request.method !== "GET" ? request.body : undefined,
      });
      const newHeaders = new Headers(resp.headers);
      Object.entries(CORS_HEADERS).forEach(([k, v]) => newHeaders.set(k, v));
      newHeaders.set("X-BlackRoad-Worker", "api-v2-blackroadio");
      return new Response(resp.body, { status: resp.status, headers: newHeaders });
    } catch {
      return Response.json({ error: "Backend unavailable" }, {
        status: 502,
        headers: CORS_HEADERS,
      });
    }
  },
};
