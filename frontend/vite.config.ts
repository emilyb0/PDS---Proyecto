import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// El backend se publica solo en IPv4: el proxy apunta a 127.0.0.1 y no a localhost (docs/guia-frontend.md, sección 1).
const API = process.env.API_URL ?? 'http://127.0.0.1:8010';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': { target: API, changeOrigin: true },
      '/health': { target: API, changeOrigin: true },
    },
  },
});
