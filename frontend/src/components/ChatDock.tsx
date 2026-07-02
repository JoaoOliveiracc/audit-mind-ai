/**
 * Gancho da fase 2: conversar com o resultado da auditoria.
 * Desabilitado no MVP — exige um endpoint de chat com o contexto do relatório.
 */
export default function ChatDock() {
  return (
    <div className="card flex items-center gap-3 opacity-60">
      <input
        className="field"
        placeholder="Perguntar sobre o resultado — em breve"
        disabled
        aria-label="Chat sobre o resultado (em breve)"
      />
      <button type="button" className="btn" disabled>
        Enviar
      </button>
    </div>
  )
}
