import { useEffect, useState, type FormEvent } from 'react'

import type { CreateAuditRequest, ProviderInfo } from '../types'
import FolderPicker from './FolderPicker'

interface Props {
  providers: ProviderInfo[]
  busy: boolean
  onStart: (req: CreateAuditRequest) => void
  /** Padrão do servidor (``AUDITOR_VULN_SCAN``); chega depois da montagem. */
  vulnScanDefault?: boolean
}

/** Formulário inicial: caminho do projeto, objetivo e provedor/modelo. */
export default function StartForm({ providers, busy, onStart, vulnScanDefault = false }: Props) {
  const [path, setPath] = useState('')
  const [goal, setGoal] = useState('')
  const [provider, setProvider] = useState('')
  const [model, setModel] = useState('')
  const [skipQuestions, setSkipQuestions] = useState(false)
  const [vulnScan, setVulnScan] = useState(vulnScanDefault)
  const [vulnScanTouched, setVulnScanTouched] = useState(false)
  // O padrão do servidor só vale enquanto o usuário não escolheu (a escolha explícita vence).
  useEffect(() => {
    if (!vulnScanTouched) setVulnScan(vulnScanDefault)
  }, [vulnScanDefault, vulnScanTouched])
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [pickerOpen, setPickerOpen] = useState(false)

  // Caminho relativo resolveria contra o cwd do processo do backend — algo que
  // o navegador não tem como ver. Exigimos absoluto pra nunca ser ambíguo.
  const isAbsolute = (p: string) => p.startsWith('/') || p.startsWith('~')
  const trimmedPath = path.trim()
  const pathError = trimmedPath && !isAbsolute(trimmedPath) ? 'Use o caminho completo, começando com / (ou ~).' : null

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!trimmedPath || pathError) return
    onStart({
      project_path: trimmedPath,
      goal: goal.trim() || undefined,
      provider: provider || undefined,
      model: model || undefined,
      interactive: !skipQuestions,
      vuln_scan: vulnScan,
    })
  }

  return (
    <form onSubmit={submit} className="card space-y-4">
      <div>
        <label htmlFor="path" className="eyebrow mb-1 block">
          Caminho do projeto
        </label>
        <div className="flex gap-2">
          <input
            id="path"
            className={`field font-mono ${pathError ? '!border-sev-critical' : ''}`}
            placeholder="/caminho/do/projeto"
            value={path}
            onChange={(e) => setPath(e.target.value)}
            aria-invalid={!!pathError}
            aria-describedby={pathError ? 'path-error' : 'path-hint'}
            autoFocus
          />
          <button type="button" className="btn shrink-0" onClick={() => setPickerOpen(true)}>
            Procurar…
          </button>
        </div>
        {pickerOpen && (
          <FolderPicker
            initialPath={trimmedPath}
            onClose={() => setPickerOpen(false)}
            onSelect={(p) => {
              setPath(p)
              setPickerOpen(false)
            }}
          />
        )}
        {pathError ? (
          <p id="path-error" className="mt-1 text-xs text-sev-critical">
            {pathError}
          </p>
        ) : (
          <p id="path-hint" className="mt-1 text-xs text-[color:var(--dim)]">
            Caminho completo no computador onde roda o Auditor-IA (ex.:{' '}
            <span className="font-mono">/Users/voce/projetos/meu-app</span>).
          </p>
        )}
      </div>

      <div>
        <label htmlFor="goal" className="eyebrow mb-1 block">
          Objetivo da auditoria <span className="normal-case tracking-normal">(opcional)</span>
        </label>
        <input
          id="goal"
          className="field"
          placeholder="Ex.: preparando para produção, foco em segurança"
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
        />
      </div>

      <label className="flex items-start gap-2 text-sm text-[color:var(--dim)]">
        <input
          type="checkbox"
          className="mt-1"
          checked={vulnScan}
          onChange={(e) => {
            setVulnScanTouched(true)
            setVulnScan(e.target.checked)
          }}
        />
        <span>Verificar dependências vulneráveis (envia nomes e versões ao OSV.dev)</span>
      </label>

      <button
        type="button"
        className="eyebrow underline-offset-4 hover:text-[color:var(--stamp)] hover:underline"
        onClick={() => setShowAdvanced((v) => !v)}
      >
        {showAdvanced ? '− opções avançadas' : '+ opções avançadas'}
      </button>

      {showAdvanced && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="provider" className="eyebrow mb-1 block">
              Provedor
            </label>
            <select
              id="provider"
              className="field"
              value={provider}
              onChange={(e) => setProvider(e.target.value)}
            >
              <option value="">padrão do servidor (.env)</option>
              {providers.map((p) => (
                <option key={p.provider} value={p.provider}>
                  {p.provider}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="model" className="eyebrow mb-1 block">
              Modelo
            </label>
            <input
              id="model"
              className="field font-mono"
              placeholder="padrão do .env"
              value={model}
              onChange={(e) => setModel(e.target.value)}
            />
          </div>
          <label className="flex items-center gap-2 text-sm text-[color:var(--dim)] sm:col-span-2">
            <input
              type="checkbox"
              checked={skipQuestions}
              onChange={(e) => setSkipQuestions(e.target.checked)}
            />
            Pular perguntas de esclarecimento (modo não interativo)
          </label>
        </div>
      )}

      <div className="flex items-center justify-between">
        <span className="eyebrow">provedor/modelo do .env · ajuste em opções avançadas</span>
        <button type="submit" className="btn btn-primary" disabled={busy || !trimmedPath || !!pathError}>
          Iniciar auditoria
        </button>
      </div>
    </form>
  )
}
