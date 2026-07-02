"use client";

import { useEffect, useRef, useState } from "react";
import { api, FindingsResponse } from "@/lib/api";
import Dashboard from "@/components/Dashboard";

const PHASE_SEQUENCE: { node: string; label: string }[] = [
  { node: "discovery", label: "Descoberta e detecção de stack" },
  { node: "plan_questions", label: "Perguntas de esclarecimento" },
  { node: "clarify", label: "Esclarecimentos" },
  { node: "planning", label: "Planejando dimensões" },
  { node: "audit", label: "Executando investigadores" },
  { node: "synthesis", label: "Consolidando e pontuando" },
  { node: "report", label: "Gerando relatório" },
];

type Question = { question: string; rationale: string };
type Investigator = { dimension: string; status: string; findings_count?: number };

export default function AuditPage({ params }: { params: { id: string } }) {
  const { id } = params;
  const [phases, setPhases] = useState<Record<string, boolean>>({});
  const [investigators, setInvestigators] = useState<Record<string, Investigator>>({});
  const [questions, setQuestions] = useState<Question[] | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [terminal, setTerminal] = useState<"completed" | "error" | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [findings, setFindings] = useState<FindingsResponse | null>(null);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const es = new EventSource(api.streamUrl(id));
    esRef.current = es;

    es.addEventListener("phase", (e) => {
      const d = JSON.parse((e as MessageEvent).data);
      setPhases((p) => ({ ...p, [d.node]: true }));
    });
    es.addEventListener("investigator", (e) => {
      const d = JSON.parse((e as MessageEvent).data);
      setInvestigators((inv) => ({ ...inv, [d.dimension]: d }));
    });
    es.addEventListener("clarification", (e) => {
      const d = JSON.parse((e as MessageEvent).data);
      setQuestions(d.questions || []);
    });
    es.addEventListener("completed", () => {
      setTerminal("completed");
      es.close();
      api.findings(id).then(setFindings).catch(() => {});
    });
    es.addEventListener("error", (e) => {
      const anyE = e as MessageEvent;
      if (anyE.data) {
        try {
          setErrorMsg(JSON.parse(anyE.data).message);
        } catch {
          /* ignore */
        }
        setTerminal("error");
        es.close();
      }
    });

    return () => es.close();
  }, [id]);

  async function submitAnswers(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      const payload: Record<string, string> = {};
      for (const q of questions || [])
        payload[q.question] = answers[q.question] || "(sem resposta)";
      await api.answer(id, payload);
      setQuestions(null);
    } finally {
      setSubmitting(false);
    }
  }

  if (terminal === "completed" && findings) {
    return <Dashboard id={id} data={findings} />;
  }

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold">Auditoria em andamento</h2>

      {/* Timeline de fases */}
      <ol className="space-y-2">
        {PHASE_SEQUENCE.map((p) => {
          const done = phases[p.node];
          return (
            <li key={p.node} className="flex items-center gap-3">
              <span className={done ? "text-low" : "text-info"}>
                {done ? "✓" : "○"}
              </span>
              <span className={done ? "" : "text-info"}>{p.label}</span>
            </li>
          );
        })}
      </ol>

      {/* Investigadores por dimensão */}
      {Object.keys(investigators).length > 0 && (
        <div className="rounded-xl border border-border bg-panel p-4">
          <h3 className="font-semibold mb-2 text-sm">Investigadores</h3>
          <ul className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-sm">
            {Object.values(investigators).map((inv) => (
              <li key={inv.dimension} className="flex items-center gap-2">
                <span>
                  {inv.status === "done" ? "✓" : inv.status === "error" ? "⚠" : "⏳"}
                </span>
                <span>{inv.dimension}</span>
                {inv.findings_count != null && (
                  <span className="text-info">({inv.findings_count})</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Esclarecimentos (human-in-the-loop) */}
      {questions && questions.length > 0 && (
        <form
          onSubmit={submitAnswers}
          className="rounded-xl border border-accent bg-panel p-5 space-y-4"
        >
          <h3 className="font-semibold">💬 Esclarecimentos</h3>
          <p className="text-sm text-info">
            O agent precisa de contexto para focar a auditoria. Responda o que puder.
          </p>
          {questions.map((q, i) => (
            <label key={i} className="block">
              <span className="text-sm">{q.question}</span>
              {q.rationale && (
                <span className="block text-xs text-info">{q.rationale}</span>
              )}
              <input
                value={answers[q.question] || ""}
                onChange={(e) =>
                  setAnswers((a) => ({ ...a, [q.question]: e.target.value }))
                }
                className="mt-1 w-full rounded-lg bg-panel2 border border-border px-3 py-2 outline-none focus:border-accent"
              />
            </label>
          ))}
          <button
            type="submit"
            disabled={submitting}
            className="rounded-lg bg-accent px-4 py-2 font-medium text-black disabled:opacity-50"
          >
            {submitting ? "Enviando…" : "Enviar e continuar"}
          </button>
        </form>
      )}

      {terminal === "error" && (
        <div className="rounded-xl border border-critical bg-panel p-5 text-sm">
          <strong className="text-critical">Falha na auditoria:</strong> {errorMsg}
        </div>
      )}
    </div>
  );
}
