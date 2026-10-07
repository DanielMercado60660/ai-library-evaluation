# Pachyderm Library operator workspace

Angular 18 and Material provide the dashboard, catalog, Assistant, benchmark
runs, analytics, report views, and trace replay.

## Development

From the repository root, follow the
[backend setup guide](../docs/development/QUICK_START.md), then:

```bash
cd frontend
npm ci
npm start
```

Open http://localhost:4200. Development mode calls backend ports 8000–8004
through the URLs in `src/environments/environment.development.ts`.
Production mode uses the nginx proxy routes configured in `nginx.conf`.

## Validation

```bash
npm run build -- --configuration production
npm test -- --watch=false --browsers=ChromeHeadless
npx playwright install chromium
npm run e2e -- --grep-invert 'live backend'
```

The Playwright server builds development mode so its API URLs match the mocked
backend routes. These tests validate UI flows with fixture responses.
For an explicitly connected backend, `npm run e2e:live` selects live tests.

The UI's patron selector is a demonstration identity mechanism. Keep real
credentials out of environment TypeScript and generated `env.js` files;
see [security notes](../SECURITY.md).
