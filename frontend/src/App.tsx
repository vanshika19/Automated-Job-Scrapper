import { useEffect, useState } from "react";
import JobsView from "./components/JobsView";
import MatchView from "./components/MatchView";
import TokenDialog from "./components/TokenDialog";
import { fetchHealth, fetchStats, type Stats } from "./api";
import { onUnauthorized } from "./auth";

type Tab = "jobs" | "match";

export default function App() {
  const [tab, setTab] = useState<Tab>("jobs");
  const [stats, setStats] = useState<Stats | null>(null);
  const [authRequired, setAuthRequired] = useState(false);
  const [tokenOpen, setTokenOpen] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    onUnauthorized(() => setTokenOpen(true));
  }, []);

  useEffect(() => {
    fetchHealth().then((h) => setAuthRequired(!!h.auth_required)).catch(() => {});
  }, [reloadKey]);

  useEffect(() => {
    fetchStats().then(setStats).catch(() => setStats(null));
  }, [tab, reloadKey]);

  return (
    <div className="min-h-full">
      <header className="sticky top-0 z-10 border-b border-white/5 bg-ink-950/80 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-accent-500 to-fuchsia-500" />
            <div>
              <div className="text-sm font-semibold tracking-tight">Job Scrapper</div>
              <div className="text-xs text-slate-400">Fintech / VC / PE / Family Office</div>
            </div>
          </div>
          <nav className="flex gap-1 rounded-xl bg-white/5 p-1 text-sm">
            {(["jobs", "match"] as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`rounded-lg px-4 py-1.5 transition-colors ${
                  tab === t ? "bg-accent-500 text-white" : "text-slate-300 hover:text-white"
                }`}
              >
                {t === "jobs" ? "Jobs" : "AI Match"}
              </button>
            ))}
          </nav>
          <div className="flex items-center gap-3 text-xs text-slate-400">
            {stats && (
              <div className="hidden md:flex items-center gap-2">
                <span className="pill">{stats.companies} companies</span>
                <span className="pill">{stats.open} open jobs</span>
              </div>
            )}
            <button
              onClick={() => setTokenOpen(true)}
              className={`btn-ghost px-3 py-1.5 ${authRequired ? "ring-1 ring-amber-400/40" : ""}`}
              title={authRequired ? "Auth enabled — set API token" : "Auth disabled (open API)"}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 1l3 7h7l-5.5 4 2 7-6.5-4-6.5 4 2-7L1 8h7z" />
              </svg>
              Token
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 py-8">
        {tab === "jobs" ? <JobsView key={`jobs-${reloadKey}`} /> : <MatchView key={`match-${reloadKey}`} />}
      </main>

      <footer className="mx-auto max-w-7xl px-6 py-8 text-xs text-slate-500">
        SQLAlchemy · FastAPI · Vite + React · Auth: {authRequired ? "required" : "open"}
      </footer>

      <TokenDialog
        open={tokenOpen}
        onClose={() => setTokenOpen(false)}
        onSaved={() => setReloadKey((k) => k + 1)}
      />
    </div>
  );
}
