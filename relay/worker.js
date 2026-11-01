// Animus Obscurus relay: a tiny mailbox for shared recommendations (Cloudflare Worker + KV).
// PUT /r/<id> (X-Key header) claims or updates a list, GET /r/<id> reads it, DELETE /r/<id> (X-Key) removes it.
// The id is random and unguessable; only a hash of the secret key is stored. Lists expire after 90 days of silence.
const ID_RE = /^[A-Za-z0-9_-]{20,40}$/;
const MAX = 256 * 1024;
const TTL = 90 * 24 * 3600;

async function sha256(text) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, "0")).join("");
}
const reply = (status, body = "") => new Response(body, { status, headers: { "Content-Type": "application/json" } });

export default {
  async fetch(req, env) {
    const m = new URL(req.url).pathname.match(/^\/r\/([^/]+)$/);
    if (!m || !ID_RE.test(m[1])) return reply(400);
    const id = m[1];
    if (req.method === "GET") {
      const doc = await env.RECS.get(`d:${id}`);
      return doc === null ? reply(404) : reply(200, doc);
    }
    if (req.method !== "PUT" && req.method !== "DELETE") return reply(405);
    const key = req.headers.get("X-Key") || "";
    if (!key) return reply(400);
    const hash = await sha256(key);
    const owner = await env.RECS.get(`k:${id}`);
    if (owner !== null && owner !== hash) return reply(403);
    if (req.method === "DELETE") {
      await Promise.all([env.RECS.delete(`d:${id}`), env.RECS.delete(`k:${id}`)]);
      return reply(200, "{}");
    }
    const body = await req.text();
    if (body.length > MAX) return reply(413);
    await Promise.all([env.RECS.put(`d:${id}`, body, { expirationTtl: TTL }), env.RECS.put(`k:${id}`, hash, { expirationTtl: TTL })]);
    return reply(200, "{}");
  },
};
