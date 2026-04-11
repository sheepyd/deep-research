import { createReadStream, existsSync } from "node:fs";
import { stat } from "node:fs/promises";
import { createServer } from "node:http";
import { extname, join, normalize } from "node:path";
import { Readable } from "node:stream";

const distDir = join(import.meta.dirname, "dist");
const backendOrigin = process.env.BACKEND_ORIGIN || "http://localhost:8000";
const port = Number(process.env.PORT || 4173);
const maxBodyBytes = 1024 * 1024;

const mimeTypes = {
  ".css": "text/css; charset=utf-8",
  ".html": "text/html; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".woff": "font/woff",
  ".woff2": "font/woff2"
};

function applySecurityHeaders(headers) {
  headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
  headers.set("X-Content-Type-Options", "nosniff");
  headers.set("X-Frame-Options", "DENY");
  headers.set("Permissions-Policy", "camera=(), microphone=(), geolocation=()");
}

async function readRequestBody(req) {
  const chunks = [];
  let total = 0;
  for await (const chunk of req) {
    total += chunk.length;
    if (total > maxBodyBytes) {
      throw new Error("Request body too large");
    }
    chunks.push(chunk);
  }
  return chunks.length ? Buffer.concat(chunks) : undefined;
}

async function proxyRequest(req, res) {
  const url = new URL(req.url || "/", backendOrigin);
  const headers = new Headers();
  for (const [key, value] of Object.entries(req.headers)) {
    if (!value || ["connection", "content-length", "host"].includes(key)) {
      continue;
    }
    headers.set(key, Array.isArray(value) ? value.join(", ") : value);
  }

  let body;
  try {
    body = req.method && ["GET", "HEAD"].includes(req.method) ? undefined : await readRequestBody(req);
  } catch {
    res.writeHead(413, { "Content-Type": "application/json; charset=utf-8" });
    res.end(JSON.stringify({ detail: "Request body too large" }));
    return;
  }

  const response = await fetch(url, {
    method: req.method,
    headers,
    body,
    duplex: body ? "half" : undefined,
    redirect: "manual"
  });

  const responseHeaders = new Headers(response.headers);
  applySecurityHeaders(responseHeaders);
  const headerObject = Object.fromEntries(responseHeaders.entries());
  if (typeof response.headers.getSetCookie === "function") {
    const cookies = response.headers.getSetCookie();
    if (cookies.length) {
      headerObject["set-cookie"] = cookies;
    }
  }

  res.writeHead(response.status, headerObject);
  if (!response.body) {
    res.end();
    return;
  }
  Readable.fromWeb(response.body).pipe(res);
}

async function serveStatic(req, res) {
  const rawPath = new URL(req.url || "/", "http://localhost").pathname;
  const candidatePath = normalize(join(distDir, rawPath === "/" ? "index.html" : rawPath));
  const safePath = candidatePath.startsWith(distDir) ? candidatePath : join(distDir, "index.html");

  let filePath = safePath;
  if (!existsSync(filePath)) {
    filePath = join(distDir, "index.html");
  } else {
    const fileStat = await stat(filePath);
    if (fileStat.isDirectory()) {
      filePath = join(filePath, "index.html");
    }
  }

  const headers = new Headers();
  headers.set("Content-Type", mimeTypes[extname(filePath)] || "application/octet-stream");
  applySecurityHeaders(headers);
  if (filePath.endsWith("index.html")) {
    headers.set("Cache-Control", "no-store");
  }

  res.writeHead(200, Object.fromEntries(headers.entries()));
  createReadStream(filePath).pipe(res);
}

createServer(async (req, res) => {
  try {
    const path = new URL(req.url || "/", "http://localhost").pathname;
    if (path.startsWith("/api/")) {
      await proxyRequest(req, res);
      return;
    }
    await serveStatic(req, res);
  } catch (error) {
    res.writeHead(500, { "Content-Type": "application/json; charset=utf-8" });
    res.end(JSON.stringify({ detail: error instanceof Error ? error.message : "Internal server error" }));
  }
}).listen(port, "0.0.0.0", () => {
  console.log(`frontend listening on http://0.0.0.0:${port}`);
});
