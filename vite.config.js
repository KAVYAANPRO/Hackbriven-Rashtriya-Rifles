import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The browser only ever talks to /api/*; Vite forwards it to the FastAPI backend.
const proxy = {
  '/api': {
    target: 'http://127.0.0.1:8000',
    changeOrigin: true,
    rewrite: (p) => p.replace(/^\/api/, ''),
  },
};

export default defineConfig({
  plugins: [react()],
  server: { port: 3000, strictPort: true, host: true, proxy },
  preview: { port: 3000, proxy },
});
