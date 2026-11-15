const { checkAuth, gh, readJson } = require("./_lib");

module.exports = async (req, res) => {
  if (!checkAuth(req, res)) return;
  try {
    const [runs, last, hist] = await Promise.all([
      gh("/actions/workflows/daily.yml/runs?per_page=10"),
      readJson("data/last_run.json").catch(() => null),
      readJson("data/history.json").catch(() => ({ videos: [], done_topics: [] })),
    ]);
    res.setHeader("Cache-Control", "no-store");
    res.json({
      runs: runs.workflow_runs.map(r => ({ id: r.id, status: r.status, conclusion: r.conclusion,
        event: r.event, started: r.run_started_at, url: r.html_url })),
      last_run: last,
      videos: (hist.videos || []).slice(-50).reverse(),
      topics_done: (hist.done_topics || []).length,
    });
  } catch (e) { res.status(500).json({ error: e.message }); }
};
