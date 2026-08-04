import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { reticle } from '@reticlehq/vite-plugin'

export default defineConfig({
  plugins: [react(), reticle({ port: 4461 })],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
      '/anomalies': 'http://localhost:8000',
      '/incidents': 'http://localhost:8000',
      '/correlations': 'http://localhost:8000',
      '/graph': 'http://localhost:8000',
      '/fixes': 'http://localhost:8000',
      '/remediation': 'http://localhost:8000',
      '/slo': 'http://localhost:8000',
      '/audit': 'http://localhost:8000',
      '/users': 'http://localhost:8000',
      '/tenants': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/metrics': 'http://localhost:8000',
      '/ai': 'http://localhost:8000',
      '/feedback': 'http://localhost:8000',
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom'],
          charts: ['recharts', 'd3'],
        },
      },
    },
  },
})
