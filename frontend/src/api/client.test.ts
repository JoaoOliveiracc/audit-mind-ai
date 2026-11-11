// Spec: .specs/features/report-chat-and-sarif/spec.md — UI-02/UI-03 (requisição do chat)
import { chatAudit, reportUrl } from './client'

function respond(status: number, body: unknown) {
  return vi.fn().mockResolvedValue(
    new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }),
  )
}

afterEach(() => vi.unstubAllGlobals())

describe('chatAudit', () => {
  it('faz POST /audits/{id}/chat com pergunta e histórico e devolve a resposta', async () => {
    const fetchMock = respond(200, { answer: 'Resposta.' })
    vi.stubGlobal('fetch', fetchMock)

    const answer = await chatAudit('a1', 'Q?', [{ role: 'user', content: 'P' }])

    expect(answer).toBe('Resposta.')
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/audits/a1/chat')
    expect(init.method).toBe('POST')
    expect(init.headers).toEqual({ 'Content-Type': 'application/json' })
    expect(JSON.parse(init.body)).toEqual({ question: 'Q?', history: [{ role: 'user', content: 'P' }] })
  })

  it('erro com detail texto (ex.: 502) vira Error com a mensagem', async () => {
    vi.stubGlobal('fetch', respond(502, { detail: 'Falha ao consultar o LLM: rate limit' }))
    await expect(chatAudit('a1', 'Q?', [])).rejects.toThrow('Falha ao consultar o LLM: rate limit')
  })

  it('erro 422 do FastAPI (detail lista) vira mensagem legível', async () => {
    vi.stubGlobal('fetch', respond(422, { detail: [{ msg: 'campo obrigatório' }, { msg: 'muito longo' }] }))
    await expect(chatAudit('a1', 'Q?', [])).rejects.toThrow('campo obrigatório; muito longo')
  })
})

describe('reportUrl', () => {
  it('aceita sarif', () => {
    expect(reportUrl('a1', 'sarif')).toBe('/audits/a1/report?format=sarif')
  })
})

describe('jsonOrThrow — corpo não-JSON sem statusText (HTTP/2)', () => {
  it('mensagem cai para "HTTP <status>" em vez de vazia', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('<html>', { status: 502 })))
    await expect(chatAudit('a1', 'Q?', [])).rejects.toThrow('HTTP 502')
  })
})
