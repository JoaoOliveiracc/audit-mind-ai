"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ProviderInfo } from "@/lib/api";

export default function NewAuditForm() {
  const router = useRouter();
  const [providers, setProviders] = useState<ProviderInfo[]>([]);
  const [projectPath, setProjectPath] = useState("");
  const [goal, setGoal] = useState("");
  const [provider, setProvider] = useState("");
  const [model, setModel] = useState("");
  const [interactive, setInteractive] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.providers().then(setProviders).catch(() => setProviders([]));
  }, []);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const audit = await api.create({
        project_path: projectPath.trim(),
        goal: goal.trim() || undefined,
        provider: provider || undefined,
        model: model.trim() || undefined,
        interactive,
      });
      router.push(`/audits/${audit.id}`);
    } catch (err: any) {
      setError(err.message || "Falha ao iniciar a auditoria.");
      setSubmitting(false);
    }
  }

  return (
    <form
      onSubmit={onSubmit}
      className="rounded-xl border border-border bg-panel p-6 space-y-4"
    >
      <h2 className="text-lg font-semibold">Nova auditoria</h2>

      <label className="block">
        <span className="text-sm text-info">Caminho do projeto</span>
        <input
          required
          value={projectPath}
          onChange={(e) => setProjectPath(e.target.value)}
          placeholder="/home/voce/projeto"
          className="mt-1 w-full rounded-lg bg-panel2 border border-border px-3 py-2 outline-none focus:border-accent"
        />
      </label>

      <label className="block">
        <span className="text-sm text-info">Objetivo (opcional)</span>
        <input
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          placeholder="Ex.: revisão de segurança pré-produção"
          className="mt-1 w-full rounded-lg bg-panel2 border border-border px-3 py-2 outline-none focus:border-accent"
        />
      </label>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <label className="block">
          <span className="text-sm text-info">Provedor (opcional)</span>
          <select
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
            className="mt-1 w-full rounded-lg bg-panel2 border border-border px-3 py-2 outline-none focus:border-accent"
          >
            <option value="">(usar padrão do .env)</option>
            {providers.map((p) => (
              <option key={p.provider} value={p.provider}>
                {p.provider}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="text-sm text-info">Modelo (opcional)</span>
          <input
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder="deepseek-chat"
            className="mt-1 w-full rounded-lg bg-panel2 border border-border px-3 py-2 outline-none focus:border-accent"
          />
        </label>
      </div>

      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={interactive}
          onChange={(e) => setInteractive(e.target.checked)}
        />
        Fazer perguntas de esclarecimento (human-in-the-loop)
      </label>

      {error && <p className="text-critical text-sm">{error}</p>}

      <button
        type="submit"
        disabled={submitting}
        className="rounded-lg bg-accent px-4 py-2 font-medium text-black disabled:opacity-50"
      >
        {submitting ? "Iniciando…" : "Iniciar auditoria"}
      </button>
    </form>
  );
}
