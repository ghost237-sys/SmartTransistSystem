import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const rootDir = fileURLToPath(new URL('.', import.meta.url))

/** Serve /app/* as the React SPA (app.html) in dev and preview. */
function spaFallbackPlugin() {
  const handler = (req, _res, next) => {
    const url = req.url?.split('?')[0] ?? ''
    if (url.startsWith('/app') && !url.includes('.') && url !== '/app.html') {
      req.url = '/app.html'
    }
    next()
  }

  return {
    name: 'smarttransit-spa-fallback',
    configureServer(server) {
      server.middlewares.use(handler)
    },
    configurePreviewServer(server) {
      server.middlewares.use(handler)
    },
  }
}

export default defineConfig({
  plugins: [react(), tailwindcss(), spaFallbackPlugin()],
  appType: 'mpa',
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  preview: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
    build: {
    rollupOptions: {
      input: {
        landing: resolve(rootDir, 'index.html'),
        app: resolve(rootDir, 'app.html'),
      },
    },
  },
})
