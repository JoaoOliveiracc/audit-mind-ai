"use client";

import { useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import {
  api,
  Finding,
  FindingsResponse,
  SEVERITY_LABEL,
  SEVERITY_ORDER,
} from "@/lib/api";

const SEV_BADGE: Record<string, string> = {
  critical: "bg-critical text-black",
  high: "bg-high text-black",
  medium: "bg-medium text-black",
  low: "bg-low text-white",
  info: "bg-info text-white",
};
const SEV_BORDER: Record<string, string> = {
  critical: "border-l-critical",
  high: "border-l-high",
  medium: "border-l-medium",
  low: "border-l-low",
  info: "border-l-info",
};

function severityRank(s: string) {
  const i = SEVERITY_ORDER.indexOf(s as any);
  return i === -1 ? 99 : i;
}

export default function Dashboard({
  id,
  data,
}: {
  id: string;
  data: FindingsResponse;
}) {
  const [sevFilter, setSevFilter] = useState("");
  const [dimFilter, setDimFilter] = useState("");

  const dimensions = useMemo(
    () => Array.from(new Set(data.findings.map((f) => f.dimension))).sort(),
    [data.findings],
  );

  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const f of data.findings) c[f.severity] = (c[f.severity] || 0) + 1;
    return c;
  }, [data.findings]);

  const findings = useMemo(() => {
    return [...data.findings]
      .filter((f) => (sevFilter ? f.severity === sevFilter : true))
      .filter((f) => (dimFilter ? f.dimension === dimFilter : true))
      .sort((a, b) => severityRank(a.severity) - severityRank(b.severity));
  }, [data.findings, sevFilter, dimFilter]);

  const score = data.health_score ?? 0;
  const scoreColor =
    score >= 75 ? "text-low" : score >= 50 ? "text-medium" : "text-critical";

  return (
    <div className="space-y-6">
      {/* Cabeçalho: score + severidades */}
      <div className="flex flex-wrap items-center gap-6 rounded-xl border border-border bg-panel p-5">
        <div>
          <div className={`text-4xl font-bold ${scoreColor}`}>
            {score}
            <span className="text-xl text-info">/100</span>
          </div>
          <div className="text-sm text-info">saúde do projeto</div>
        </div>
        <div className="flex flex-wrap gap-2">
          {SEVERITY_ORDER.map((s) => (
            <span
              key={s}
              className={`rounded-full px-3 py-1 text-xs font-semibold ${SEV_BADGE[s]}`}
            >
              {SEVERITY_LABEL[s]}: {counts[s] || 0}
            </span>
          ))}
        </div>
        <div className="ml-auto flex gap-3 text-sm">
          <a className="text-accent underline" href={api.reportUrl(id, "html")} target="_blank">
            Relatório HTML
          </a>
          <a className="text-accent underline" href={api.reportUrl(id, "md")} target="_blank">
            Markdown
          </a>
        </div>
      </div>

      {/* Resumo executivo */}
      {data.executive_summary && (
        <section className="rounded-xl border border-border bg-panel p-5">
          <h3 className="font-semibold mb-2">Resumo executivo</h3>
          <div className="prose-invert text-sm">
            <ReactMarkdown>{data.executive_summary}</ReactMarkdown>
          </div>
        </section>
      )}

      {/* Filtros */}
      <div className="flex flex-wrap gap-3">
        <select
          value={sevFilter}
          onChange={(e) => setSevFilter(e.target.value)}
          className="rounded-lg bg-panel2 border border-border px-3 py-2 text-sm"
        >
          <option value="">Todas as severidades</option>
          {SEVERITY_ORDER.map((s) => (
            <option key={s} value={s}>
              {SEVERITY_LABEL[s]}
            </option>
          ))}
        </select>
        <select
          value={dimFilter}
          onChange={(e) => setDimFilter(e.target.value)}
          className="rounded-lg bg-panel2 border border-border px-3 py-2 text-sm"
        >
          <option value="">Todas as dimensões</option>
          {dimensions.map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </select>
        <span className="ml-auto self-center text-sm text-info">
          {findings.length} achado(s)
        </span>
      </div>

      {/* Lista de achados */}
      <div className="space-y-3">
        {findings.length === 0 && (
          <p className="text-info text-sm">Nenhum achado com esses filtros.</p>
        )}
        {findings.map((f, i) => (
          <FindingCard key={i} f={f} />
        ))}
      </div>
    </div>
  );
}

function FindingCard({ f }: { f: Finding }) {
  const [open, setOpen] = useState(false);
  return (
    <div
      className={`rounded-lg border border-border border-l-4 ${SEV_BORDER[f.severity]} bg-panel p-4`}
    >
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-3 text-left"
      >
        <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${SEV_BADGE[f.severity]}`}>
          {SEVERITY_LABEL[f.severity]}
        </span>
        <span className="font-medium">{f.title}</span>
        <span className="ml-auto text-xs text-info">
          {f.dimension}
          {f.file ? ` · ${f.file}${f.line ? `:${f.line}` : ""}` : ""}
        </span>
      </button>
      {open && (
        <div className="mt-3 space-y-3 text-sm">
          <p>{f.description}</p>
          {f.evidence && (
            <pre className="overflow-x-auto rounded-lg bg-black/40 p-3 text-xs">
              {f.evidence}
            </pre>
          )}
          <div className="rounded-lg bg-panel2 p-3">
            <strong>Recomendação:</strong> {f.recommendation}
          </div>
          <div className="text-xs text-info">
            Confiança: {Math.round((f.confidence || 0) * 100)}%
          </div>
        </div>
      )}
    </div>
  );
}
