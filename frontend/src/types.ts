// Espelha o contrato da API (src/auditor/api): REST + eventos SSE nomeados.

export type Severity = 'critical' | 'high' | 'medium' | 'low' | 'info'

export interface Finding {
  dimension: string
  title: string
  severity: Severity
  description: string
  recommendation: string
  file?: string | null
  line?: number | null
  evidence?: string | null
  confidence: number
  // Anexados pelos nós verify/adversarial (backend upstream).
  verified?: boolean
  verification_note?: string | null
  judged?: 'confirmed' | 'uncertain'
  judge_rationale?: string | null
}

/** Estatística final da verificação determinística de evidência (nó `verify`). */
export interface VerificationSummary {
  enabled?: boolean
  verified: number
  unverified: number
  rejected: number
  rejected_titles?: string[]
}

/** Estatística final da verificação adversarial (nó `adversarial`, opcional). */
export interface AdversarialSummary {
  enabled?: boolean
  judged: number
  confirmed: number
  refuted: number
  uncertain: number
  refuted_titles?: string[]
}

export interface ClarifyingQuestion {
  question: string
  rationale: string
}

export interface StackProfile {
  languages?: Record<string, number>
  frameworks?: string[]
  package_managers?: string[]
  marker_files?: string[]
  total_files?: number
  total_loc?: number
  has_tests?: boolean
  has_ci?: boolean
  has_docker?: boolean
  has_git?: boolean
}

export interface DimensionSummary {
  dimension: string
  summary: string
}

// ---- Eventos SSE (GET /audits/{id}/stream, campo `event` nomeado) ----
export interface PhaseEvent {
  node: string
  label: string
  status: 'done'
}

export interface InvestigatorEvent {
  type: 'investigator'
  dimension: string
  status: 'start' | 'done' | 'error' | 'empty'
  index: number
  total: number
  findings_count?: number
  message?: string
}

export interface ClarificationEvent {
  questions: ClarifyingQuestion[]
}

/** Evento ao vivo do nó `verify` (checagem determinística de evidência). */
export interface VerificationEvent {
  type: 'verification'
  verified: number
  unverified: number
  rejected: number
}

/** Evento ao vivo do nó `adversarial` (juiz LLM cético). */
export interface AdversarialEvent {
  type: 'adversarial'
  judged: number
  confirmed: number
  refuted: number
  uncertain: number
}

export interface CompletedEvent {
  health_score: number | null
  counts: Record<string, number>
}

export interface ErrorEvent {
  message: string
}

// ---- REST ----
export interface CreateAuditRequest {
  project_path: string
  goal?: string
  provider?: string
  model?: string
  interactive: boolean
}

export interface AuditSummary {
  id: string
  status: string
  project_path: string
  goal?: string | null
  provider?: string | null
  model?: string | null
  created_at: string
  health_score?: number | null
  counts?: Record<string, number> | null
  error?: string | null
}

export interface FindingsPayload {
  findings: Finding[]
  dimension_summaries: DimensionSummary[]
  health_score: number | null
  executive_summary: string
  stack_profile: StackProfile
  verification?: VerificationSummary
  adversarial?: AdversarialSummary
}

export interface ProviderInfo {
  provider: string
  package: string
  credential_env: string | null
}

export interface BrowseEntry {
  name: string
  path: string
}

export interface BrowseResponse {
  path: string
  parent: string | null
  entries: BrowseEntry[]
}
