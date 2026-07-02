import { useEffect, useState } from 'react'

import { browseFs } from '../api/client'
import type { BrowseEntry } from '../types'

interface Props {
  /** Pasta inicial (ex.: último valor do campo, se já parecer um caminho). */
  initialPath?: string
  onSelect: (path: string) => void
  onClose: () => void
}

/** Picker de pasta: navega o filesystem do backend (o navegador não expõe
 * caminhos absolutos de um `<input type=file>`, então a listagem vem do servidor). */
export default function FolderPicker({ initialPath, onSelect, onClose }: Props) {
  const [path, setPath] = useState<string | null>(null)
  const [parent, setParent] = useState<string | null>(null)
  const [entries, setEntries] = useState<BrowseEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = (target?: string) => {
    setLoading(true)
    setError(null)
    browseFs(target)
      .then((r) => {
        setPath(r.path)
        setParent(r.parent)
        setEntries(r.entries)
      })
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load(initialPath && (initialPath.startsWith('/') || initialPath.startsWith('~')) ? initialPath : undefined)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Escolher pasta do projeto"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className="card flex w-full max-w-lg flex-col !p-0">
        <div className="border-b border-[color:var(--line)] p-4">
          <p className="eyebrow mb-1">Escolher pasta</p>
          <p className="truncate font-mono text-sm" title={path ?? ''}>
            {path ?? '…'}
          </p>
        </div>

        <div className="max-h-80 overflow-y-auto p-2">
          {loading && <p className="p-3 text-sm text-[color:var(--dim)]">Carregando…</p>}
          {error && (
            <p className="p-3 text-sm text-sev-critical" role="alert">
              {error}
            </p>
          )}
          {!loading && !error && (
            <ul className="space-y-0.5">
              {parent && (
                <li>
                  <button
                    type="button"
                    className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm text-[color:var(--dim)] hover:bg-[color:var(--ink)] hover:text-[color:var(--text)]"
                    onClick={() => load(parent)}
                  >
                    <span className="font-mono">‹</span> ..
                  </button>
                </li>
              )}
              {entries.map((entry) => (
                <li key={entry.path}>
                  <button
                    type="button"
                    className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm hover:bg-[color:var(--ink)]"
                    onClick={() => load(entry.path)}
                  >
                    <span className="font-mono text-[color:var(--dim)]">›</span> {entry.name}
                  </button>
                </li>
              ))}
              {entries.length === 0 && !parent && (
                <li className="px-2 py-1.5 text-sm text-[color:var(--dim)]">Pasta vazia.</li>
              )}
            </ul>
          )}
        </div>

        <div className="flex items-center justify-end gap-2 border-t border-[color:var(--line)] p-3">
          <button type="button" className="btn" onClick={onClose}>
            Cancelar
          </button>
          <button
            type="button"
            className="btn btn-primary"
            disabled={!path}
            onClick={() => path && onSelect(path)}
          >
            Selecionar esta pasta
          </button>
        </div>
      </div>
    </div>
  )
}
