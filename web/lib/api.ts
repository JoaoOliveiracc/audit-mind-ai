// Cliente da API do Auditor-IA (backend FastAPI).

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8020";

export type ProviderInfo = {
  provider: string;
  package: string;
  credential_env: string | null;
};

export type AuditSummary = {
  id: string;
  status: string;
  project_path: string;
  goal: string | null;
  provider: string | null;
  model: string | null;
  created_at: string;
  health_score: number | null;
  counts: Record<string, number> | null;
  error: string | null;
};

export type Finding = {
  dimension: string;
  title: string;
  severity: "critical" | "high" | "medium" | "low" | "info";
  description: string;
  recommendation: string;
  file: string | null;
  line: number | null;
  evidence: string | null;
  confidence: number;
};

export type FindingsResponse = {
  findings: Finding[];
  dimension_summaries: { dimension: string; summary: string }[];
  health_score: number | null;
  executive_summary: string;
  stack_profile: Record<string, unknown>;
};

export type CreateAuditPayload = {
  project_path: string;
  goal?: string;
  provider?: string;
  model?: string;
  interactive: boolean;
};

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error((detail as any)?.detail || `Erro ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  providers: () => fetch(`${API_URL}/providers`).then(json<ProviderInfo[]>),
  listAudits: () => fetch(`${API_URL}/audits`).then(json<AuditSummary[]>),
  getAudit: (id: string) => fetch(`${API_URL}/audits/${id}`).then(json<AuditSummary>),
  findings: (id: string) =>
    fetch(`${API_URL}/audits/${id}/findings`).then(json<FindingsResponse>),
  create: (payload: CreateAuditPayload) =>
    fetch(`${API_URL}/audits`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).then(json<AuditSummary>),
  answer: (id: string, answers: Record<string, string>) =>
    fetch(`${API_URL}/audits/${id}/answers`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answers }),
    }).then(json<{ status: string }>),
  reportUrl: (id: string, format: "html" | "md") =>
    `${API_URL}/audits/${id}/report?format=${format}`,
  streamUrl: (id: string) => `${API_URL}/audits/${id}/stream`,
};

export const SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"] as const;
export const SEVERITY_LABEL: Record<string, string> = {
  critical: "Crítico",
  high: "Alto",
  medium: "Médio",
  low: "Baixo",
  info: "Info",
};
