/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Dev: o Vite serve o frontend e faz proxy das rotas da API (incl. o SSE de
// /audits/{id}/stream) para o backend FastAPI em :8020 (porta padrão do
// `auditor serve`). Prod: `vite build` -> dist/ (estático; o `auditor serve`
// ainda NÃO serve o dist/ — ver G42 em DOCUMENTACAO.md).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // A API não usa prefixo /api — proxy por rota (inclui o SSE de /audits).
    proxy: Object.fromEntries(
      ['/audits', '/providers', '/health', '/fs'].map((route) => [
        route,
        { target: 'http://127.0.0.1:8020', changeOrigin: true },
      ]),
    ),
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
  },
})
