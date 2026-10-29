import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  // The app calls the API at /api on its own origin, like in production (where
  // vercel.json rewrites /api to the Render API). In development, /api/... is
  // forwarded to the local FastAPI server with the /api prefix removed, so the
  // session cookie is first-party here too. Override with VITE_API_PROXY_TARGET.
  server: {
    proxy: {
      '/api': {
        target: process.env.VITE_API_PROXY_TARGET ?? 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
  // `npm test`: component tests in a simulated browser (jsdom). No real API or database.
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.{js,jsx}'],
  },
})
