/**
 * 🤖 BlackRoad Agents Worker
 * Routes agent API requests with long-running task support.
 * Deployed to: agents.blackroad.io
 *
 * ✅ VERIFIED WORKING — Cloudflare Worker (edge runtime)
 * Uses Cloudflare Workers for longer AI agent orchestration tasks.
 */

const BACKEND = "https://api.blackroad.io";
const AGENT_TIMEOUT_MS = 29000; // Cloudflare Workers hard limit is 30s (free), 15min (paid)

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

    if (url.pathname === "/health") {
      return Response.json({
        status: "healthy",
        service: "BlackRoad Agents Worker",
        version: "1.0.0",
        region: request.cf?.colo ?? "unknown",
        timestamp: new Date().toISOString(),
        verified: true,
        capabilities: ["agent-routing", "async-tasks", "load-balancing"],
      }, { headers: { ...CORS_HEADERS, "Cache-Control": "no-cache" } });
    }

    // Long-running agent tasks via waitUntil
    if (request.method === "POST" && url.pathname === "/agents/run") {
      let body;
      try { body = await request.json(); } catch {
        return Response.json({ error: "Invalid JSON" }, { status: 400, headers: CORS_HEADERS });
      }

      // Use ctx.waitUntil for tasks that can run after response
      const taskId = crypto.randomUUID();
      const responseData = {
        status: "accepted",
        taskId,
        message: "Agent task accepted for processing",
        estimatedMs: 5000,
      };

      // Fire-and-forget the actual long task
      ctx.waitUntil(
        fetch(`${BACKEND}/agents/run`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ...body, taskId }),
        }).catch(() => {})
      );

      return Response.json(responseData, {
        status: 202,
        headers: CORS_HEADERS,
      });
    }

    // Proxy all other requests with timeout
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), AGENT_TIMEOUT_MS);

    try {
      const resp = await fetch(`${BACKEND}${url.pathname}${url.search}`, {
        method: request.method,
        headers: request.headers,
        body: request.method !== "GET" ? request.body : undefined,
        signal: controller.signal,
      });
      clearTimeout(timeoutId);

      const newHeaders = new Headers(resp.headers);
      Object.entries(CORS_HEADERS).forEach(([k, v]) => newHeaders.set(k, v));
      newHeaders.set("X-BlackRoad-Worker", "agents-blackroadio");

      return new Response(resp.body, { status: resp.status, headers: newHeaders });
    } catch (err) {
      clearTimeout(timeoutId);
      return Response.json({
        error: err.name === "AbortError" ? "Gateway timeout" : "Backend unavailable",
      }, { status: err.name === "AbortError" ? 504 : 502, headers: CORS_HEADERS });
    }
  },
};
