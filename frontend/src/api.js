import { getToken, notifyUnauthorized } from "./auth";
const enc = (v) => v === undefined || v === null || v === "" ? "" : encodeURIComponent(String(v));
async function request(path, init) {
    const token = getToken();
    const headers = new Headers(init?.headers || {});
    if (token)
        headers.set("Authorization", `Bearer ${token}`);
    const r = await fetch(path, { ...init, headers });
    if (r.status === 401) {
        notifyUnauthorized();
        throw new Error("Unauthorized: API token required or invalid.");
    }
    return r;
}
export async function fetchHealth() {
    const r = await fetch("/api/health");
    return r.json();
}
export async function fetchStats() {
    const r = await request("/api/stats");
    if (!r.ok)
        throw new Error(`stats ${r.status}`);
    return r.json();
}
export async function fetchJobs(params) {
    const qs = Object.entries(params)
        .filter(([, v]) => v !== undefined && v !== "")
        .map(([k, v]) => `${k}=${enc(v)}`)
        .join("&");
    const r = await request(`/api/jobs${qs ? `?${qs}` : ""}`);
    if (!r.ok)
        throw new Error(`jobs ${r.status}`);
    return r.json();
}
export async function matchResume(file, top_k = 25) {
    const fd = new FormData();
    fd.append("resume", file);
    fd.append("top_k", String(top_k));
    const r = await request("/api/match", { method: "POST", body: fd });
    if (!r.ok) {
        const txt = await r.text();
        throw new Error(`match ${r.status}: ${txt}`);
    }
    return r.json();
}
