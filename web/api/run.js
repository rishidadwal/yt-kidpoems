const { checkAuth, gh } = require("./_lib");

module.exports = async (req, res) => {
  if (req.method !== "POST") return res.status(405).json({ error: "POST only" });
  if (!checkAuth(req, res)) return;
  const upload = (req.body && req.body.upload) === "no" ? "no" : "yes";
  try {
    await gh("/actions/workflows/daily.yml/dispatches", {
      method: "POST", body: JSON.stringify({ ref: "main", inputs: { upload } }),
      headers: { "Content-Type": "application/json" },
    });
    res.json({ ok: true, upload });
  } catch (e) { res.status(500).json({ error: e.message }); }
};
