import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { reticle } from '@reticlehq/vite-plugin'

export default defineConfig({
  plugins: [react(), reticle({ port: 4461 })],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      '/ws': {
        target: 'ws://localhost:8080',
        ws: true,
      },
      '/anomalies': 'http://localhost:8080',
      '/incidents': 'http://localhost:8080',
      '/correlations': 'http://localhost:8080',
      '/graph': 'http://localhost:8080',
      '/fixes': 'http://localhost:8080',
      '/remediation': 'http://localhost:8080',
      '/slo': 'http://localhost:8080',
      '/audit': 'http://localhost:8080',
      '/users': 'http://localhost:8080',
      '/tenants': 'http://localhost:8080',
      '/health': 'http://localhost:8080',
      '/metrics': 'http://localhost:8080',
      '/ai': 'http://localhost:8080',
      '/feedback': 'http://localhost:8080',
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
