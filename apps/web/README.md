# KUANGUARD web

Next.js/React/TypeScript public, customer, learner, internal, and v1.1 owner portfolio interfaces. No external activation.

```powershell
npm ci --ignore-scripts
npm run dev
```

The local app listens at `http://127.0.0.1:3180`. The FastAPI service must be available at `http://127.0.0.1:8180`. `/api/*` is a same-origin rewrite, and development profiles are shown only when the real `/auth/dev/profiles` endpoint enables them.

```powershell
npm run typecheck
npm run test
npm run build
$env:DEPLOYMENT_SURFACE = 'local'
npm start
```

`npm start` uses Next standalone, default port 3180. `PORT` and `HOSTNAME` can be specified for the appropriate local/container binding. The API rewrite target is selected at **build** time through `API_INTERNAL_URL`.

Deployment surfaces: `public` for Vercel public/customer/learner, `internal` for the protected admin container, `local` for the combined local environment. Vercel rejects internal/local surfaces, and public production rejects admin/portfolio/internal API paths even through alternate HTTP host aliases or encoded paths. Internal APIs separately require Access and application authorization.

HTTP contract checks against the local development server:

```powershell
node tests/http-smoke.mjs
node tests/operations-smoke.mjs
```

The first script creates one synthetic inquiry with `example.invalid` email and checks role/CSRF isolation. The operations script creates labelled synthetic XLSX recipient, campaign, questionnaire, ticket and scope-change records; it validates unknown delivery reconciliation, optimistic concurrency, finite entitlement grants and customer acceptance through the same-origin API. Its temporary assessment batch is cancelled to release the reservation, with history preserved. Neither script sends email, charges money, or invokes browser automation. Production surface checks use a separately launched local standalone server at port 3181 with `DEPLOYMENT_SURFACE=public`:

```powershell
node tests/public-surface-smoke.mjs
```

Evidence is in `evidence/`. Browser interaction and 390/768/1440 screenshots remain unverified because CUA's required browser security policy check was unavailable; no alternate browser workaround was used. See `../../docs/route-map.md` and `../../docs/design-system.md` for implemented routes and remaining activation/UX gaps.
