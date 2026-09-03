# API Guide

Interactive OpenAPI documentation is at `http://localhost:8000/docs`.

Major routes:

- `POST /api/v1/auth/login` (`/dev-login` exists only in explicit development JWT mode)
- `GET /api/v1/cases` and `GET /api/v1/cases/{case_number}`
- `GET /api/v1/cases/{case_number}/timeline` and `/graph`
- `POST /api/v1/documents`
- `POST /api/v1/documents/{id}/versions`
- `GET /api/v1/documents/{id}/versions` and `/download`
- `GET /api/v1/evidence` and `GET /api/v1/evidence/{id}/passport`
- `POST /api/v1/evidence/{id}/custody`
- `POST /api/v1/verification/document`
- `POST /api/v1/ai/case/{case_number}/brief` and `/ask`
- `GET /api/v1/search` and `POST /api/v1/search/case`
- `POST /api/v1/access/grants`, `/break-glass`, and `/grants/{id}/revoke`
- `GET /api/v1/audit`
- `POST /api/v1/blockchain/checkpoints`
- `GET /api/v1/blockchain/merkle/{event_id}/proof`
- `GET /api/v1/cases/{case_number}/verification-report`
- `GET /api/v1/public/verify/{opaque_token}`
- `GET /api/v1/integrations`, `GET /api/v1/health`, and the orchestrator alias `GET /health`

Except health and opaque public verification, endpoints require a bearer token. Resource authorization is applied after identity resolution and before evidence retrieval.
