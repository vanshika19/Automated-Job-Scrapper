import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState } from "react";
import JobsView from "./components/JobsView";
import MatchView from "./components/MatchView";
import TokenDialog from "./components/TokenDialog";
import { fetchHealth, fetchStats } from "./api";
import { onUnauthorized } from "./auth";
export default function App() {
    const [tab, setTab] = useState("jobs");
    const [stats, setStats] = useState(null);
    const [authRequired, setAuthRequired] = useState(false);
    const [tokenOpen, setTokenOpen] = useState(false);
    const [reloadKey, setReloadKey] = useState(0);
    useEffect(() => {
        onUnauthorized(() => setTokenOpen(true));
    }, []);
    useEffect(() => {
        fetchHealth().then((h) => setAuthRequired(!!h.auth_required)).catch(() => { });
    }, [reloadKey]);
    useEffect(() => {
        fetchStats().then(setStats).catch(() => setStats(null));
    }, [tab, reloadKey]);
    return (_jsxs("div", { className: "min-h-full", children: [_jsx("header", { className: "sticky top-0 z-10 border-b border-white/5 bg-ink-950/80 backdrop-blur", children: _jsxs("div", { className: "mx-auto flex max-w-7xl items-center justify-between px-6 py-4", children: [_jsxs("div", { className: "flex items-center gap-3", children: [_jsx("div", { className: "h-8 w-8 rounded-lg bg-gradient-to-br from-accent-500 to-fuchsia-500" }), _jsxs("div", { children: [_jsx("div", { className: "text-sm font-semibold tracking-tight", children: "Job Scrapper" }), _jsx("div", { className: "text-xs text-slate-400", children: "Fintech / VC / PE / Family Office" })] })] }), _jsx("nav", { className: "flex gap-1 rounded-xl bg-white/5 p-1 text-sm", children: ["jobs", "match"].map((t) => (_jsx("button", { onClick: () => setTab(t), className: `rounded-lg px-4 py-1.5 transition-colors ${tab === t ? "bg-accent-500 text-white" : "text-slate-300 hover:text-white"}`, children: t === "jobs" ? "Jobs" : "AI Match" }, t))) }), _jsxs("div", { className: "flex items-center gap-3 text-xs text-slate-400", children: [stats && (_jsxs("div", { className: "hidden md:flex items-center gap-2", children: [_jsxs("span", { className: "pill", children: [stats.companies, " companies"] }), _jsxs("span", { className: "pill", children: [stats.open, " open jobs"] })] })), _jsxs("button", { onClick: () => setTokenOpen(true), className: `btn-ghost px-3 py-1.5 ${authRequired ? "ring-1 ring-amber-400/40" : ""}`, title: authRequired ? "Auth enabled — set API token" : "Auth disabled (open API)", children: [_jsx("svg", { width: "14", height: "14", viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "2", children: _jsx("path", { d: "M12 1l3 7h7l-5.5 4 2 7-6.5-4-6.5 4 2-7L1 8h7z" }) }), "Token"] })] })] }) }), _jsx("main", { className: "mx-auto max-w-7xl px-6 py-8", children: tab === "jobs" ? _jsx(JobsView, {}, `jobs-${reloadKey}`) : _jsx(MatchView, {}, `match-${reloadKey}`) }), _jsxs("footer", { className: "mx-auto max-w-7xl px-6 py-8 text-xs text-slate-500", children: ["SQLAlchemy \u00B7 FastAPI \u00B7 Vite + React \u00B7 Auth: ", authRequired ? "required" : "open"] }), _jsx(TokenDialog, { open: tokenOpen, onClose: () => setTokenOpen(false), onSaved: () => setReloadKey((k) => k + 1) })] }));
}
