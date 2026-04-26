import { useState } from "react";
import { matchResume, type MatchResult } from "../api";

export default function MatchView() {
  const [file, setFile] = useState<File | null>(null);
  const [topK, setTopK] = useState(25);
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<MatchResult[]>([]);
  const [resumeChars, setResumeChars] = useState(0);
  const [err, setErr] = useState<string | null>(null);

  const onSubmit = async () => {
    if (!file) return;
    setLoading(true);
    setErr(null);
    try {
      const r = await matchResume(file, topK);
      setResults(r.results);
      setResumeChars(r.resume_chars);
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  };

  const scoreBar = (score: number) => {
    const pct = Math.max(0, Math.min(1, score)) * 100;
    return (
      <div className="flex w-32 items-center gap-2">
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/10">
          <div
            className="h-full rounded-full bg-gradient-to-r from-accent-500 to-fuchsia-500"
            style={{ width: `${pct}%` }}
          />
        </div>
        <span className="w-10 text-right text-xs tabular-nums text-slate-300">
          {score.toFixed(2)}
        </span>
      </div>
    );
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[420px_1fr]">
      <div className="card p-6">
        <h2 className="text-lg font-semibold">Resume → Jobs</h2>
        <p className="mt-1 text-sm text-slate-400">
          Upload a PDF (or .txt) resume. We embed it and rank open jobs by cosine similarity.
        </p>

        <label className="mt-6 block">
          <span className="text-xs uppercase tracking-wider text-slate-400">Resume file</span>
          <div className="mt-2 rounded-xl border border-dashed border-white/10 bg-ink-800/40 p-6 text-center">
            <input
              type="file"
              accept=".pdf,.txt,.md"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="block w-full text-sm text-slate-300 file:mr-3 file:rounded-lg file:border-0 file:bg-accent-500 file:px-4 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-accent-400"
            />
            {file && (
              <div className="mt-3 text-xs text-slate-400">
                {file.name} · {(file.size / 1024).toFixed(1)} KB
              </div>
            )}
          </div>
        </label>

        <label className="mt-6 block">
          <span className="text-xs uppercase tracking-wider text-slate-400">Top K</span>
          <input
            type="number"
            min={5}
            max={200}
            value={topK}
            onChange={(e) => setTopK(parseInt(e.target.value, 10) || 25)}
            className="input mt-2"
          />
        </label>

        <button onClick={onSubmit} disabled={!file || loading} className="btn-primary mt-6 w-full">
          {loading ? "Scoring..." : "Match jobs"}
        </button>

        {err && <div className="mt-3 text-sm text-rose-400">{err}</div>}
        {!err && resumeChars > 0 && (
          <div className="mt-3 text-xs text-slate-500">Extracted {resumeChars.toLocaleString()} characters.</div>
        )}
      </div>

      <div className="card overflow-hidden">
        <div className="max-h-[75vh] overflow-auto">
          <table className="min-w-full text-sm">
            <thead className="sticky top-0 bg-ink-800/95 text-left text-xs uppercase tracking-wider text-slate-400">
              <tr>
                <th className="px-4 py-3">Score</th>
                <th className="px-4 py-3">Company</th>
                <th className="px-4 py-3">Title</th>
                <th className="px-4 py-3">Location</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {results.map((r) => (
                <tr key={r.fingerprint} className="hover:bg-white/5">
                  <td className="px-4 py-3">{scoreBar(r.score)}</td>
                  <td className="px-4 py-3 font-medium text-slate-100">{r.company}</td>
                  <td className="px-4 py-3 text-slate-200">{r.title}</td>
                  <td className="px-4 py-3 text-slate-300">{r.location || "—"}</td>
                  <td className="px-4 py-3 text-right">
                    {r.url && (
                      <a className="text-accent-400 hover:underline" href={r.url} target="_blank" rel="noreferrer">
                        Open ↗
                      </a>
                    )}
                  </td>
                </tr>
              ))}
              {!loading && results.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-12 text-center text-slate-500">
                    Upload a resume to see ranked job matches.
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
