import type {
  AuditSummary,
  BrowseResponse,
  CreateAuditRequest,
  FindingsPayload,
  ProviderInfo,
} from '../types'

async function jsonOrThrow(res: Response): Promise<any> {
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail ?? detail
    } catch {
      /* corpo não-JSON: mantém statusText */
    }
    throw new Error(detail)
  }
  return res.json()
}

export async function getProviders(): Promise<ProviderInfo[]> {
  return jsonOrThrow(await fetch('/providers'))
}

export async function listAudits(): Promise<AuditSummary[]> {
  return jsonOrThrow(await fetch('/audits'))
}

export async function getAudit(auditId: string): Promise<AuditSummary> {
  return jsonOrThrow(await fetch(`/audits/${auditId}`))
}

export async function createAudit(req: CreateAuditRequest): Promise<AuditSummary> {
  return jsonOrThrow(
    await fetch('/audits', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    }),
  )
}

export async function submitAnswers(
  auditId: string,
  answers: Record<string, string>,
): Promise<void> {
  await jsonOrThrow(
    await fetch(`/audits/${auditId}/answers`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ answers }),
    }),
  )
}

/** Retoma uma auditoria `interrupted` do último checkpoint (404/409/400 viram Error). */
export async function resumeAudit(auditId: string): Promise<AuditSummary> {
  return jsonOrThrow(await fetch(`/audits/${auditId}/resume`, { method: 'POST' }))
}

/** Exclui a auditoria (204). Erros (404/409/500) viram Error com o `detail` da API. */
export async function deleteAudit(auditId: string): Promise<void> {
  const res = await fetch(`/audits/${auditId}`, { method: 'DELETE' })
  if (!res.ok) await jsonOrThrow(res)
}

export async function getFindings(auditId: string): Promise<FindingsPayload> {
  return jsonOrThrow(await fetch(`/audits/${auditId}/findings`))
}

export function reportUrl(auditId: string, format: 'md' | 'html'): string {
  return `/audits/${auditId}/report?format=${format}`
}

export async function browseFs(path?: string): Promise<BrowseResponse> {
  const qs = path ? `?path=${encodeURIComponent(path)}` : ''
  return jsonOrThrow(await fetch(`/fs/browse${qs}`))
}
