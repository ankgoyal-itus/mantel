import { defineConfig } from 'vitest/config'

// No plugins: the tested modules are plain TypeScript, so the legacy/React
// pipeline would only slow the run down.
export default defineConfig({
  test: {
    environment: 'node',
    include: ['src/**/*.test.{ts,tsx}'],
  },
})
