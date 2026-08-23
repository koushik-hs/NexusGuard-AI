import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {},
  },
  define: {
    // Required for react-force-graph-2d (uses process.env)
    'process.env': {},
  },
  optimizeDeps: {
    include: ['react-force-graph-2d'],
  },
})
