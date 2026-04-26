import { getToken, notifyUnauthorized } from "./auth";

export type Job = {
  fingerprint: string;
  company: string;
  title: string;
  url: string;
  location: string;
  department: string;
  description: string;
  source: string;
  posted_at: string;
  scraped_at: string;
  last_seen_at: string;
  status: string;
};

export type JobsResp = { total: number; items: Job[] };

export type Stats = {
  companies: number;
  jobs: number;
  open: number;
  by_source: Record<string, number>;
};

export type Health = { ok: boolean; auth_required?: boolean; error?: string };

export type MatchResult = Job & { score: number };

const enc = (v: string | number | boolean | undefined | null) =>
  v === undefined || v === null || v === "" ? "" : encodeURIComponent(String(v));

async function request(path: string, init?: RequestInit): Promise<Response> {
  const token = getToken();
  const headers = new Headers(init?.headers || {});
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const r = await fetch(path, { ...init, headers });
  if (r.status === 401) {
    notifyUnauthorized();
    throw new Error("Unauthorized: API token required or invalid.");
  }
  return r;
}

export async function fetchHealth(): Promise<Health> {
  const r = await fetch("/api/health");
  return r.json();
}

export async function fetchStats(): Promise<Stats> {
  const r = await request("/api/stats");
  if (!r.ok) throw new Error(`stats ${r.status}`);
  return r.json();
}

export async function fetchJobs(params: {
  q?: string;
  source?: string;
  location?: string;
  company?: string;
  limit?: number;
  offset?: number;
}): Promise<JobsResp> {
  const qs = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== "")
    .map(([k, v]) => `${k}=${enc(v as any)}`)
    .join("&");
  const r = await request(`/api/jobs${qs ? `?${qs}` : ""}`);
  if (!r.ok) throw new Error(`jobs ${r.status}`);
  return r.json();
}

export async function matchResume(file: File, top_k = 25): Promise<{ resume_chars: number; results: MatchResult[] }> {
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
