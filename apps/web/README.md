# NyayaGraph web

The Next.js frontend for the Phase 1?6 NyayaGraph MVP. It provides a responsive, role-aware investigation workspace using the real FastAPI contract.

## Run locally

```bash
cd apps/web
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1 npm run dev
```

Open [http://localhost:3000](http://localhost:3000). Use a development identity such as `io@nyaya.local` with `NyayaDemo!2026`.

## API expectations

The API URL is configurable through `NEXT_PUBLIC_API_URL` and defaults to `http://localhost:8000/api/v1`. The client sends the development-login token as a bearer token for all protected calls. It calls the supplied auth, case, timeline, graph, passport and local-file verification endpoints.

The UI deliberately degrades with clear messaging if an authorized record is unavailable, restricted or the API is offline. Seeded visual context is used only to keep the demo navigable; it is never presented as a successful API response.

## Quality check

```bash
npm run lint
npm run build
```
