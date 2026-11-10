import { useState, type FormEvent } from 'react'
import Markdown from 'react-markdown'

import { chatAudit, type ChatTurn } from '../api/client'

/** Trocas anteriores reenviadas a cada pergunta (limite da API). */
const MAX_HISTORY = 10

/** Chat sobre o relatório da auditoria concluída. A conversa vive só nesta tela (G42). */
export default function ChatDock({ auditId }: { auditId: string }) {
  const [turns, setTurns] = useState<ChatTurn[]>([])
  const [question, setQuestion] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const trimmed = question.trim()

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!trimmed || pending) return
    setPending(true)
    setError(null)
    try {
      const answer = await chatAudit(auditId, trimmed, turns.slice(-MAX_HISTORY))
      setTurns((prev) => [
        ...prev,
        { role: 'user', content: trimmed },
        { role: 'assistant', content: answer },
      ])
      setQuestion('')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setPending(false)
    }
  }

  return (
    <section className="card space-y-3">
      <p className="eyebrow">Perguntar sobre o resultado</p>
      {turns.length > 0 && (
        <ol className="space-y-2 text-sm">
          {turns.map((t, i) => (
            <li
              key={i}
              className={t.role === 'user' ? 'font-medium' : 'text-[color:var(--dim)] [&_strong]:text-[color:var(--stamp)]'}
            >
              {t.role === 'user' ? t.content : <Markdown>{t.content}</Markdown>}
            </li>
          ))}
        </ol>
      )}
      {error && (
        <p className="break-words text-sm text-sev-critical" role="alert">
          {error}
        </p>
      )}
      <form className="flex items-center gap-3" onSubmit={handleSubmit}>
        <input
          className="field"
          placeholder="Ex.: qual o achado mais grave e como corrigir?"
          aria-label="Pergunta sobre o resultado"
          maxLength={2000}
          value={question}
          disabled={pending}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <button type="submit" className="btn" disabled={pending || !trimmed}>
          Enviar
        </button>
      </form>
    </section>
  )
}
