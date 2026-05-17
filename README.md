# OrangeHRM + ReqRes — Playwright TypeScript Allure Framework

A production-focused Playwright + TypeScript automation framework with Allure reporting, split by test layers (unit/api/ui/e2e), and CI quality gates.

## Quality strategy and best practices implemented
- Single framework for UI and API automation (Playwright).
- Layered execution model: `@unit`, `@api`, `@ui`, `@e2e` projects.
- Page Object Model for UI (`framework/pages/login.page.ts`).
- API client abstraction for reuse and maintainability (`framework/api/reqres.client.ts`).
- Shared fixture injection (`framework/fixtures/test-fixtures.ts`).
- Environment centralization (`framework/config/env.ts`).
- Failure diagnostics enabled by default (trace/video/screenshot).
- Allure + Playwright HTML reporting.
- CI matrix running each quality layer independently.

## Structure
- `framework/config/` → env configuration
- `framework/pages/` → page objects
- `framework/api/` → API clients
- `framework/fixtures/` → typed fixtures
- `tests/unit/` → unit tests
- `tests/api/` → API scenario tests
- `tests/ui/` → UI scenario tests
- `tests/e2e/` → cross-layer tests
- `features/` → scenario-based feature documentation

## Run locally
```bash
npm ci
npx playwright install --with-deps chromium
npm run test:unit
npm run test:api
npm run test:ui
npm run test:e2e
npm run test
npm run allure:generate
npm run allure:open
```

## Reporting
- Allure raw: `allure-results/`
- Allure HTML: `allure-report/`
- Playwright HTML: `playwright-report/`

## CI
Workflow: `.github/workflows/playwright-allure.yml`
- Matrix quality gates: `unit`, `api`, `ui`, `e2e`
- Uploads per-layer Allure + Playwright reports.
