import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState } from "react";
import { fetchJobs } from "../api";
const SOURCES = ["", "ats", "career", "linkedin"];
export default function JobsView() {
    const [q, setQ] = useState("");
    const [source, setSource] = useState("");
    const [location, setLocation] = useState("");
    const [items, setItems] = useState([]);
    const [total, setTotal] = useState(0);
    const [loading, setLoading] = useState(false);
    const [err, setErr] = useState(null);
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
    const sourceBadge = (s) => {
        if (s.startsWith("ats"))
            return "bg-emerald-500/15 text-emerald-300";
        if (s === "career")
            return "bg-sky-500/15 text-sky-300";
        if (s === "linkedin")
            return "bg-indigo-500/15 text-indigo-300";
        return "bg-white/5 text-slate-300";
    };
    return (_jsxs("div", { className: "space-y-4", children: [_jsxs("div", { className: "card p-4", children: [_jsxs("div", { className: "grid gap-3 md:grid-cols-[1fr_180px_200px_auto]", children: [_jsx("input", { className: "input", placeholder: "Search title or description...", value: q, onChange: (e) => setQ(e.target.value) }), _jsx("select", { className: "input", value: source, onChange: (e) => setSource(e.target.value), children: SOURCES.map((s) => (_jsx("option", { value: s, children: s ? s : "all sources" }, s))) }), _jsx("input", { className: "input", placeholder: "Location contains...", value: location, onChange: (e) => setLocation(e.target.value) }), _jsx("button", { className: "btn-ghost", onClick: () => { setQ(""); setSource(""); setLocation(""); }, children: "Reset" })] }), _jsxs("div", { className: "mt-3 text-xs text-slate-400", children: [loading ? "Loading..." : `${items.length} of ${total} matching jobs`, err && _jsx("span", { className: "ml-3 text-rose-400", children: err })] })] }), _jsx("div", { className: "card overflow-hidden", children: _jsx("div", { className: "max-h-[70vh] overflow-auto", children: _jsxs("table", { className: "min-w-full text-sm", children: [_jsx("thead", { className: "sticky top-0 bg-ink-800/95 text-left text-xs uppercase tracking-wider text-slate-400", children: _jsxs("tr", { children: [_jsx("th", { className: "px-4 py-3", children: "Company" }), _jsx("th", { className: "px-4 py-3", children: "Title" }), _jsx("th", { className: "px-4 py-3", children: "Location" }), _jsx("th", { className: "px-4 py-3", children: "Source" }), _jsx("th", { className: "px-4 py-3", children: "Posted" }), _jsx("th", { className: "px-4 py-3" })] }) }), _jsxs("tbody", { className: "divide-y divide-white/5", children: [items.map((j) => (_jsxs("tr", { className: "hover:bg-white/5", children: [_jsx("td", { className: "px-4 py-3 font-medium text-slate-100", children: j.company }), _jsx("td", { className: "px-4 py-3 text-slate-200", children: j.title }), _jsx("td", { className: "px-4 py-3 text-slate-300", children: j.location || "—" }), _jsx("td", { className: "px-4 py-3", children: _jsx("span", { className: `pill ${sourceBadge(j.source)}`, children: j.source }) }), _jsx("td", { className: "px-4 py-3 text-slate-400", children: j.posted_at?.slice(0, 10) || "—" }), _jsx("td", { className: "px-4 py-3 text-right", children: j.url && (_jsx("a", { className: "text-accent-400 hover:underline", href: j.url, target: "_blank", rel: "noreferrer", children: "Open \u2197" })) })] }, j.fingerprint))), !loading && items.length === 0 && (_jsx("tr", { children: _jsxs("td", { colSpan: 6, className: "px-4 py-8 text-center text-slate-500", children: ["No jobs found. Run ", _jsx("code", { className: "rounded bg-white/5 px-1", children: "python -m job_scraper scrape" }), " first."] }) }))] })] }) }) })] }));
}
