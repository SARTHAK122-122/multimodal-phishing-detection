import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Dev convenience: the dashboard calls /api/* same-origin, and Vite
    // proxies it to the Spring Boot backend. Production (nginx in Docker)
    // proxies the same /api path, so the bundle never hardcodes a host.
    proxy: {
      '/api': 'http://localhost:8088',
    },
  },
  preview: {
    proxy: {
      '/api': 'http://localhost:8088',
    },
  },
})
