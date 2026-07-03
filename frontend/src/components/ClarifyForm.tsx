import { useState, type FormEvent } from 'react'

import type { ClarifyingQuestion } from '../types'

interface Props {
  questions: ClarifyingQuestion[]
  onSubmit: (answers: Record<string, string>) => void
}

/** Perguntas de esclarecimento respondidas inline, dentro da conversa. */
export default function ClarifyForm({ questions, onSubmit }: Props) {
  const [answers, setAnswers] = useState<string[]>(() => questions.map(() => ''))

  const submit = (e: FormEvent) => {
    e.preventDefault()
    const map: Record<string, string> = {}
    questions.forEach((q, i) => {
      map[q.question] = answers[i].trim() || '(sem resposta)'
    })
    onSubmit(map)
  }

  const skipAll = () => {
    const map: Record<string, string> = {}
    questions.forEach((q) => {
      map[q.question] = '(sem resposta)'
    })
    onSubmit(map)
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      {questions.map((q, i) => (
        <div key={q.question}>
          <p className="text-sm font-medium">
            {i + 1}. {q.question}
          </p>
          {q.rationale && (
            <p className="mt-0.5 text-xs text-[color:var(--dim)]">{q.rationale}</p>
          )}
          <input
            className="field mt-2"
            placeholder="Sua resposta (Enter em branco = pular)"
            value={answers[i]}
            onChange={(e) =>
              setAnswers((prev) => prev.map((a, j) => (j === i ? e.target.value : a)))
            }
          />
        </div>
      ))}
      <div className="flex gap-2">
        <button type="submit" className="btn btn-primary">
          Enviar respostas
        </button>
        <button type="button" className="btn" onClick={skipAll}>
          Pular todas
        </button>
      </div>
    </form>
  )
}
