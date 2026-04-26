import { useEffect, useMemo, useState } from "react";
import { fetchJobs, type Job } from "../api";

const SOURCES = ["", "ats", "career", "linkedin"];

export default function JobsView() {
  const [q, setQ] = useState("");
  const [source, setSource] = useState("");
  const [location, setLocation] = useState("");
  const [items, setItems] = useState<Job[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    const handle = setTimeout(() => {
      setLoading(true);
      setErr(null);
      fetchJobs({ q, source, location, limit: 200 })
        .then((r) => {
          setItems(r.items);
          setTotal(r.total);
        })
        .catch((e) => setErr(String(e)))
        .finally(() => setLoading(false));
    }, 200);
    return () => clearTimeout(handle);
  }, [q, source, location]);

  const sourceBadge = (s: string) => {
    if (s.startsWith("ats")) return "bg-emerald-500/15 text-emerald-300";
    if (s === "career") return "bg-sky-500/15 text-sky-300";
    if (s === "linkedin") return "bg-indigo-500/15 text-indigo-300";
    return "bg-white/5 text-slate-300";
  };

  return (
    <div className="space-y-4">
      <div className="card p-4">
        <div className="grid gap-3 md:grid-cols-[1fr_180px_200px_auto]">
          <input
            className="input"
            placeholder="Search title or description..."
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <select className="input" value={source} onChange={(e) => setSource(e.target.value)}>
            {SOURCES.map((s) => (
              <option key={s} value={s}>{s ? s : "all sources"}</option>
            ))}
          </select>
          <input
            className="input"
            placeholder="Location contains..."
            value={location}
            onChange={(e) => setLocation(e.target.value)}
          />
          <button className="btn-ghost" onClick={() => { setQ(""); setSource(""); setLocation(""); }}>
            Reset
          </button>
        </div>
        <div className="mt-3 text-xs text-slate-400">
          {loading ? "Loading..." : `${items.length} of ${total} matching jobs`}
          {err && <span className="ml-3 text-rose-400">{err}</span>}
        </div>
      </div>

      <div className="card overflow-hidden">
        <div className="max-h-[70vh] overflow-auto">
          <table className="min-w-full text-sm">
            <thead className="sticky top-0 bg-ink-800/95 text-left text-xs uppercase tracking-wider text-slate-400">
              <tr>
                <th className="px-4 py-3">Company</th>
                <th className="px-4 py-3">Title</th>
                <th className="px-4 py-3">Location</th>
                <th className="px-4 py-3">Source</th>
                <th className="px-4 py-3">Posted</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {items.map((j) => (
                <tr key={j.fingerprint} className="hover:bg-white/5">
                  <td className="px-4 py-3 font-medium text-slate-100">{j.company}</td>
                  <td className="px-4 py-3 text-slate-200">{j.title}</td>
                  <td className="px-4 py-3 text-slate-300">{j.location || "—"}</td>
                  <td className="px-4 py-3">
                    <span className={`pill ${sourceBadge(j.source)}`}>{j.source}</span>
                  </td>
                  <td className="px-4 py-3 text-slate-400">{j.posted_at?.slice(0, 10) || "—"}</td>
                  <td className="px-4 py-3 text-right">
                    {j.url && (
                      <a className="text-accent-400 hover:underline" href={j.url} target="_blank" rel="noreferrer">
                        Open ↗
                      </a>
                    )}
                  </td>
                </tr>
              ))}
              {!loading && items.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                    No jobs found. Run <code className="rounded bg-white/5 px-1">python -m job_scraper scrape</code> first.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
