import { defineConfig } from 'vite';

const base = process.env.BASE_URL ?? '/';

export default defineConfig({
  root: '.',
  publicDir: 'public',
  base,
  build: {
    outDir: 'dist',
    emptyOutDir: true
  }
});
