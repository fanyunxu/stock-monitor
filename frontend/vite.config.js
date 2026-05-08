import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  base: '/static/',
  build: {
    outDir: resolve(__dirname, '../static'),
    emptyOutDir: false,
    rollupOptions: {
      external: ['/static/bootstrap.bundle.min.js'],
    },
  },
})
