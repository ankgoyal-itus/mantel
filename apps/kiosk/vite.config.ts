import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The kiosk talks only to the API, which Vite proxies in dev so the iPad
// needs a single host:port.
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000' },
    },
  },
  build: {
    // The API serves this directory in Prompt 8. Both iPads run iOS 18.7.9.
    target: 'safari17',
    outDir: '../../services/api/static',
    emptyOutDir: true,
  },
})
