"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import NewAuditForm from "@/components/NewAuditForm";
import { api, AuditSummary } from "@/lib/api";

const STATUS_LABEL: Record<string, string> = {
  running: "em execução",
  waiting_input: "aguardando resposta",
  completed: "concluída",
  error: "erro",
};

export default function HomePage() {
  const [audits, setAudits] = useState<AuditSummary[]>([]);

  useEffect(() => {
    api.listAudits().then(setAudits).catch(() => setAudits([]));
  }, []);

  return (
    <div className="space-y-8">
      <NewAuditForm />

      <section>
        <h2 className="text-lg font-semibold mb-3">Histórico</h2>
        {audits.length === 0 ? (
          <p className="text-info text-sm">Nenhuma auditoria ainda.</p>
        ) : (
          <ul className="space-y-2">
            {audits.map((a) => (
              <li key={a.id}>
                <Link
                  href={`/audits/${a.id}`}
                  className="flex items-center justify-between rounded-lg border border-border bg-panel px-4 py-3 hover:border-accent"
                >
                  <span className="truncate">
                    <span className="font-mono text-sm">{a.project_path}</span>
                    {a.goal && <span className="text-info text-sm"> — {a.goal}</span>}
                  </span>
                  <span className="text-sm text-info shrink-0 ml-4">
                    {STATUS_LABEL[a.status] || a.status}
                    {a.health_score != null && ` · ${a.health_score}/100`}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
