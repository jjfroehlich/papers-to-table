import path from 'node:path'
import { fileURLToPath } from 'node:url'

const rootDir = fileURLToPath(new URL('.', import.meta.url))
const frontendNodeModules = path.resolve(rootDir, '../../../app/frontend/node_modules')
const dep = (name: string) => path.join(frontendNodeModules, name)

export default {
  base: './',
  resolve: {
    alias: [
      { find: /^react$/, replacement: dep('react') },
      { find: /^react\/(.*)$/, replacement: dep('react/$1') },
      { find: /^react-dom$/, replacement: dep('react-dom') },
      { find: /^react-dom\/(.*)$/, replacement: dep('react-dom/$1') },
      { find: /^pdfjs-dist$/, replacement: dep('pdfjs-dist') },
      { find: /^pdfjs-dist\/(.*)$/, replacement: dep('pdfjs-dist/$1') },
      { find: /^@testing-library\/react$/, replacement: dep('@testing-library/react') },
      { find: /^@testing-library\/jest-dom\/vitest$/, replacement: dep('@testing-library/jest-dom/vitest') },
    ],
  },
  build: {
    outDir: '../assets/review_app',
    emptyOutDir: true,
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    pool: 'threads',
    fileParallelism: false,
    maxWorkers: 1,
  },
}
