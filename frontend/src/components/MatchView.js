import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState } from "react";
import { matchResume } from "../api";
export default function MatchView() {
    const [file, setFile] = useState(null);
    const [topK, setTopK] = useState(25);
    const [loading, setLoading] = useState(false);
    const [results, setResults] = useState([]);
    const [resumeChars, setResumeChars] = useState(0);
    const [err, setErr] = useState(null);
    const onSubmit = async () => {
        if (!file)
            return;
        setLoading(true);
        setErr(null);
        try {
            const r = await matchResume(file, topK);
            setResults(r.results);
            setResumeChars(r.resume_chars);
        }
        catch (e) {
            setErr(String(e));
        }
        finally {
            setLoading(false);
        }
    };
    const scoreBar = (score) => {
        const pct = Math.max(0, Math.min(1, score)) * 100;
        return (_jsxs("div", { className: "flex w-32 items-center gap-2", children: [_jsx("div", { className: "h-1.5 flex-1 overflow-hidden rounded-full bg-white/10", children: _jsx("div", { className: "h-full rounded-full bg-gradient-to-r from-accent-500 to-fuchsia-500", style: { width: `${pct}%` } }) }), _jsx("span", { className: "w-10 text-right text-xs tabular-nums text-slate-300", children: score.toFixed(2) })] }));
    };
    return (_jsxs("div", { className: "grid gap-6 lg:grid-cols-[420px_1fr]", children: [_jsxs("div", { className: "card p-6", children: [_jsx("h2", { className: "text-lg font-semibold", children: "Resume \u2192 Jobs" }), _jsx("p", { className: "mt-1 text-sm text-slate-400", children: "Upload a PDF (or .txt) resume. We embed it and rank open jobs by cosine similarity." }), _jsxs("label", { className: "mt-6 block", children: [_jsx("span", { className: "text-xs uppercase tracking-wider text-slate-400", children: "Resume file" }), _jsxs("div", { className: "mt-2 rounded-xl border border-dashed border-white/10 bg-ink-800/40 p-6 text-center", children: [_jsx("input", { type: "file", accept: ".pdf,.txt,.md", onChange: (e) => setFile(e.target.files?.[0] ?? null), className: "block w-full text-sm text-slate-300 file:mr-3 file:rounded-lg file:border-0 file:bg-accent-500 file:px-4 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-accent-400" }), file && (_jsxs("div", { className: "mt-3 text-xs text-slate-400", children: [file.name, " \u00B7 ", (file.size / 1024).toFixed(1), " KB"] }))] })] }), _jsxs("label", { className: "mt-6 block", children: [_jsx("span", { className: "text-xs uppercase tracking-wider text-slate-400", children: "Top K" }), _jsx("input", { type: "number", min: 5, max: 200, value: topK, onChange: (e) => setTopK(parseInt(e.target.value, 10) || 25), className: "input mt-2" })] }), _jsx("button", { onClick: onSubmit, disabled: !file || loading, className: "btn-primary mt-6 w-full", children: loading ? "Scoring..." : "Match jobs" }), err && _jsx("div", { className: "mt-3 text-sm text-rose-400", children: err }), !err && resumeChars > 0 && (_jsxs("div", { className: "mt-3 text-xs text-slate-500", children: ["Extracted ", resumeChars.toLocaleString(), " characters."] }))] }), _jsx("div", { className: "card overflow-hidden", children: _jsx("div", { className: "max-h-[75vh] overflow-auto", children: _jsxs("table", { className: "min-w-full text-sm", children: [_jsx("thead", { className: "sticky top-0 bg-ink-800/95 text-left text-xs uppercase tracking-wider text-slate-400", children: _jsxs("tr", { children: [_jsx("th", { className: "px-4 py-3", children: "Score" }), _jsx("th", { className: "px-4 py-3", children: "Company" }), _jsx("th", { className: "px-4 py-3", children: "Title" }), _jsx("th", { className: "px-4 py-3", children: "Location" }), _jsx("th", { className: "px-4 py-3" })] }) }), _jsxs("tbody", { className: "divide-y divide-white/5", children: [results.map((r) => (_jsxs("tr", { className: "hover:bg-white/5", children: [_jsx("td", { className: "px-4 py-3", children: scoreBar(r.score) }), _jsx("td", { className: "px-4 py-3 font-medium text-slate-100", children: r.company }), _jsx("td", { className: "px-4 py-3 text-slate-200", children: r.title }), _jsx("td", { className: "px-4 py-3 text-slate-300", children: r.location || "—" }), _jsx("td", { className: "px-4 py-3 text-right", children: r.url && (_jsx("a", { className: "text-accent-400 hover:underline", href: r.url, target: "_blank", rel: "noreferrer", children: "Open \u2197" })) })] }, r.fingerprint))), !loading && results.length === 0 && (_jsx("tr", { children: _jsx("td", { colSpan: 5, className: "px-4 py-12 text-center text-slate-500", children: "Upload a resume to see ranked job matches." }) }))] })] }) }) })] }));
}
