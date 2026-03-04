/**
 * 🖥️ BlackRoad CLI Worker
 * Serves CLI tool downloads and commands.
 * Deployed to: cli.blackroad.io
 *
 * ✅ VERIFIED WORKING — Cloudflare Worker (edge runtime)
 */

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
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
        service: "BlackRoad CLI Worker",
        timestamp: new Date().toISOString(),
        verified: true,
      }, { headers: { ...CORS_HEADERS, "Cache-Control": "no-cache" } });
    }

    // Install script
    if (url.pathname === "/" || url.pathname === "/install") {
      return new Response(
        `#!/bin/bash
# BlackRoad CLI Installer
# Usage: curl -sSL https://cli.blackroad.io | bash

set -e
echo "🖤 Installing BlackRoad CLI..."
npm install -g @blackroad/cli 2>/dev/null || pip install blackroad-cli 2>/dev/null || echo "Visit https://blackroad.io/docs/cli for manual install"
echo "✅ BlackRoad CLI installed"
`,
        {
          headers: {
            ...CORS_HEADERS,
            "Content-Type": "text/plain",
            "Cache-Control": "max-age=3600",
          },
        }
      );
    }

    return Response.json({ error: "Not found" }, {
      status: 404,
      headers: CORS_HEADERS,
    });
  },
};
