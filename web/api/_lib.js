// Shared helpers for the Vercel serverless functions (Node 18+, no dependencies).
const crypto = require("crypto");

function checkAuth(req, res) {
  const want = process.env.DASHBOARD_PASSWORD || "";
  const got = req.headers["x-dashboard-password"] || "";
  const ok = want.length >= 8 && got.length === want.length &&
    crypto.timingSafeEqual(Buffer.from(got), Buffer.from(want));
  if (!ok) { res.status(401).json({ error: "wrong password" }); return false; }
  return true;
}

async function gh(path, init = {}) {
  const repo = process.env.GITHUB_REPO;           // e.g. "rishi/kidpoems"
  const token = process.env.GITHUB_TOKEN;         // fine-grained PAT: Actions RW, Contents R
  if (!repo || !token) throw new Error("GITHUB_REPO / GITHUB_TOKEN not set on Vercel");
  const r = await fetch(`https://api.github.com/repos/${repo}${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${token}`, Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "kidpoems-dashboard", ...(init.headers || {}) },
  });
  if (!r.ok && r.status !== 204) throw new Error(`GitHub ${r.status}: ${(await r.text()).slice(0, 200)}`);
  return r.status === 204 ? null : r.json();
}

async function readJson(file) {
  const f = await gh(`/contents/${file}?ref=main`);
  return JSON.parse(Buffer.from(f.content, "base64").toString("utf8"));
}

module.exports = { checkAuth, gh, readJson };
