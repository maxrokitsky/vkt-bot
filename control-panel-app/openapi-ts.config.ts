import { defineConfig } from '@hey-api/openapi-ts';

export default defineConfig({
  runtimeConfigPath: './src/hey-api.ts',
  input: {
    path: 'http://localhost:8765/openapi.json',
  },
  output: 'src/client',
  plugins: [
    '@hey-api/typescript',
    '@hey-api/client-ofetch',
    '@tanstack/vue-query',
  ]
});
