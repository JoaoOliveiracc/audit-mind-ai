import type {
  ClarifyingQuestion,
  CompletedEvent,
  FindingsPayload,
  InvestigatorEvent,
  PhaseEvent,
  StackProfile,
} from '../types'

export interface DimensionProgress {
  dimension: string
  status: InvestigatorEvent['status']
  index: number
  total: number
  findings_count?: number
  message?: string
}

export type Status = 'idle' | 'running' | 'awaiting_clarify' | 'finished' | 'error'

export interface AuditUIState {
  status: Status
  /** Nós do grafo já concluídos (evento `phase` do SSE). */
  phasesDone: string[]
  stackProfile: StackProfile | null
  dimensions: Record<string, DimensionProgress>
  dimensionOrder: string[]
  pendingClarify: ClarifyingQuestion[] | null
  clarifyAnswered: boolean
  completed: CompletedEvent | null
  results: FindingsPayload | null
  error: string | null
}

export const initialState: AuditUIState = {
  status: 'idle',
  phasesDone: [],
  stackProfile: null,
  dimensions: {},
  dimensionOrder: [],
  pendingClarify: null,
  clarifyAnswered: false,
  completed: null,
  results: null,
  error: null,
}

export type Action =
  | { type: 'START' }
  | { type: 'PHASE'; event: PhaseEvent }
  | { type: 'SNAPSHOT'; stackProfile: StackProfile }
  | { type: 'INVESTIGATOR'; event: InvestigatorEvent }
  | { type: 'CLARIFY'; questions: ClarifyingQuestion[] }
  | { type: 'CLARIFY_SUBMITTED' }
  | { type: 'COMPLETED'; event: CompletedEvent }
  | { type: 'RESULTS'; payload: FindingsPayload }
  | { type: 'ERROR'; message: string }
  | { type: 'RESET' }

export function auditReducer(state: AuditUIState, action: Action): AuditUIState {
  switch (action.type) {
    case 'START':
      return { ...initialState, status: 'running' }
    case 'RESET':
      return initialState
    case 'PHASE': {
      const { node } = action.event
      const phasesDone = state.phasesDone.includes(node)
        ? state.phasesDone
        : [...state.phasesDone, node]
      return { ...state, phasesDone }
    }
    case 'SNAPSHOT':
      return { ...state, stackProfile: action.stackProfile }
    case 'INVESTIGATOR': {
      const e = action.event
      const dimensions = {
        ...state.dimensions,
        [e.dimension]: {
          dimension: e.dimension,
          status: e.status,
          index: e.index,
          total: e.total,
          findings_count: e.findings_count,
          message: e.message,
        },
      }
      const dimensionOrder = state.dimensionOrder.includes(e.dimension)
        ? state.dimensionOrder
        : [...state.dimensionOrder, e.dimension]
      return { ...state, dimensions, dimensionOrder }
    }
    case 'CLARIFY':
      return { ...state, status: 'awaiting_clarify', pendingClarify: action.questions }
    case 'CLARIFY_SUBMITTED':
      return { ...state, status: 'running', pendingClarify: null, clarifyAnswered: true }
    case 'COMPLETED':
      return { ...state, status: 'finished', completed: action.event }
    case 'RESULTS':
      return { ...state, results: action.payload }
    case 'ERROR':
      return { ...state, status: 'error', error: action.message }
    default:
      return state
  }
}
