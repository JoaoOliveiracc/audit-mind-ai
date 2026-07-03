import type {
  AuditSummary,
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

export async function getFindings(auditId: string): Promise<FindingsPayload> {
  return jsonOrThrow(await fetch(`/audits/${auditId}/findings`))
}

export function reportUrl(auditId: string, format: 'md' | 'html'): string {
  return `/audits/${auditId}/report?format=${format}`
}
