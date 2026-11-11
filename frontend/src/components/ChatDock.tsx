import { useState, type FormEvent } from 'react'
import Markdown from 'react-markdown'

import { chatAudit, type ChatTurn } from '../api/client'
import { errorNotice, noticeText, useI18n } from '../i18n/I18nProvider'
import type { Notice } from '../types'

/** Trocas anteriores reenviadas a cada pergunta (limite da API). */
const MAX_HISTORY = 10

/** Chat sobre o relatório da auditoria concluída. A conversa vive só nesta tela (G42). */
export default function ChatDock({ auditId }: { auditId: string }) {
  const { t } = useI18n()
  const [turns, setTurns] = useState<ChatTurn[]>([])
  const [question, setQuestion] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<Notice | null>(null)

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
      setError(errorNotice(err))
    } finally {
      setPending(false)
    }
  }

  return (
    <section className="card space-y-3">
      <p className="eyebrow">{t.chat.title}</p>
      {turns.length > 0 && (
        <ol className="space-y-2 text-sm">
          {turns.map((turn, i) => (
            <li
              key={i}
              className={turn.role === 'user' ? 'font-medium' : 'text-[color:var(--dim)] [&_strong]:text-[color:var(--stamp)]'}
            >
              {turn.role === 'user' ? turn.content : <Markdown>{turn.content}</Markdown>}
            </li>
          ))}
        </ol>
      )}
      {error && (
        <p className="break-words text-sm text-sev-critical" role="alert">
          {noticeText(t, error)}
        </p>
      )}
      <form className="flex items-center gap-3" onSubmit={handleSubmit}>
        <input
          className="field"
          placeholder={t.chat.placeholder}
          aria-label={t.chat.inputLabel}
          maxLength={2000}
          value={question}
          disabled={pending}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <button type="submit" className="btn" disabled={pending || !trimmed}>
          {t.chat.send}
        </button>
      </form>
    </section>
  )
}
