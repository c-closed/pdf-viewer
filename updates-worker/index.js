// PDF 뷰어 자동 업데이트 Worker
//
// 라우트:
//   GET /                -> latest.json
//   GET /latest.json     -> 최신 버전 manifest (R2 객체 "latest.json")
//   GET /download/<file> -> R2 객체 "releases/<file>" 를 다운로드로 제공
//   GET /health          -> "ok"
//   GET /<key>           -> R2 객체 "<key>" 그대로 제공
//
// manifest 형식:
//   { "version": "1.2.0", "url": "https://.../download/PDFViewer-Setup-1.2.0.exe",
//     "sha256": "<hex>", "size": 12345, "pub_date": "2026-10-13T00:00:00Z" }

const MANIFEST_KEY = "latest.json";
const RELEASE_PREFIX = "releases/";

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = decodeURIComponent(url.pathname);

    if (path === "/" || path === "/latest.json") {
      return serveManifest(env);
    }
    if (path === "/health") {
      return new Response("ok", { status: 200 });
    }
    if (path.startsWith("/download/")) {
      const name = path.slice("/download/".length);
      return serveFile(env, RELEASE_PREFIX + name, name);
    }
    const key = path.replace(/^\/+/, "");
    return serveFile(env, key, key.split("/").pop());
  },
};

async function serveManifest(env) {
  const obj = await env.BUCKET.get(MANIFEST_KEY);
  if (!obj) return json({ error: "manifest not found" }, 404);
  return new Response(await obj.text(), {
    headers: {
      "content-type": "application/json; charset=utf-8",
      // 엣지 캐시(짧게) — 릴리스 직후에도 빨리 반영
      "cache-control": "public, max-age=300",
      "access-control-allow-origin": "*",
    },
  });
}

async function serveFile(env, key, filename) {
  const obj = await env.BUCKET.get(key);
  if (!obj) return json({ error: "not found", key }, 404);

  const headers = new Headers();
  obj.writeHttpMetadata(headers);
  headers.set("etag", obj.httpEtag);
  if (!headers.get("content-type")) {
    headers.set("content-type", "application/octet-stream");
  }
  headers.set("content-disposition", `attachment; filename="${filename}"`);
  // 파일명에 버전이 포함되므로 영구 캐시 가능
  headers.set("cache-control", "public, max-age=31536000, immutable");
  headers.set("access-control-allow-origin", "*");
  return new Response(obj.body, { headers });
}

function json(obj, status) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "access-control-allow-origin": "*",
    },
  });
}
