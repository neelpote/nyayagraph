# NyayaGraph Project Context

Last updated: 2026-09-04

This is the current engineering handoff for NyayaGraph. It records implemented behavior, operating assumptions, local-demo facts, security boundaries, and remaining gaps. It excludes private reasoning and production secrets. Detailed decisions and runtime paths remain in `DECISIONS.md` and `FLOW.md`.

## Product and Scope

**Product:** NyayaGraph — Privacy-Preserving Verifiable Case Intelligence & Evidence Management Platform  
**Tagline:** From Case Files to Verifiable Case Intelligence.  
**Problem:** SIH26190, Ministry of Home Affairs, Smart India Hackathon 2026.

NyayaGraph is an intelligence and provenance layer above CCTNS, ICJS, eSakshya, eCourts, eForensics, eProsecution, and ePrisons. It does not replace those systems. The main journey is:

```text
Sign in → enter Case ID → open the authorized case workspace → inspect evidence,
documents, citations, timeline, graph, custody, integrity, and verification.
```

The flagship Case ID is `MH-PUNE-2026-00142`.

The supported deliverable is a local, fictional-data MVP. Government API access and real criminal-justice records are unavailable and are not required. Every seeded record is explicitly fictional. Connector cards are simulated and never claim live government connectivity.

AI is read-only investigative support. It does not determine guilt, assign guilt probability, file charges, change custody, grant access, modify evidence, or make legal conclusions.

## Repository and Documentation

- GitHub: <https://github.com/neelpote/nyayagraph>
- Default branch: `main`
- `README.md`: overview and quick start
- `SETUP.md`: platform setup
- `STATUS.md`: current delivery state
- `DECISIONS.md`: append-only engineering decisions
- `FLOW.md`: real runtime call paths
- `docs/ARCHITECTURE.md`: architecture
- `docs/THREAT_MODEL.md`: threats and controls
- `docs/SECURITY.md`: security notes
- `docs/DEMO.md`: demo guide
- `docs/API.md`: API guide
- `docs/DEPLOYMENT.md`: deployment notes

Main directories:

```text
apps/web                       Next.js frontend
apps/api                       FastAPI backend
blockchain/fabric              Fabric chaincode and local-network scripts
blockchain/public-anchor       Solidity, Hardhat, tests, deployment
infra                          Infrastructure and production overlay
seed                           Demo artifacts/data tooling
scripts                        Verification and operations
.github/workflows/ci.yml       Launch-readiness CI
.github/dependabot.yml         Dependency monitoring
```

## Architecture

The implemented application boundary is:

```text
Router → Service → Domain/Policy → Repository or Provider → Infrastructure
```

Provider boundaries exist where infrastructure genuinely varies:

- `EvidenceStorageProvider`: MinIO, encrypted IPFS, local test storage
- `ProvenanceLedger`: Hyperledger Fabric, marked database-development ledger
- `PublicAnchorProvider`: Hardhat/local EVM, Polygon Amoy, mock tests
- `LLMProvider` and embedding provider: deterministic demo or compatible HTTP provider
- graph provider: PostgreSQL source of truth, optional Neo4j
- identity provider: Keycloak/OIDC, explicit development JWT mode

## Frontend

- Next.js 16 App Router
- React 19 and TypeScript
- Tailwind CSS and Lucide icons
- Responsive investigation workspace
- Native fetch wrapper
- Tab-scoped session state

Pages:

```text
/login                 /dashboard
/cases                 /cases/[caseId]
/documents             /evidence
/evidence/[evidenceId] /custody
/ai                    /verification
/audit                 /access
/integrations
```

The case workspace provides Overview, Timeline, People, Evidence, Documents, AI Insights, Knowledge Graph, Custody, Audit, and Verification experiences where data exists.

Clicking a demo identity on `/login` fills both email and the demo password. The user still presses **Access workspace** to authenticate.

## Backend and Data

- Python 3.12
- FastAPI, Pydantic, SQLAlchemy, Alembic, Uvicorn
- PostgreSQL with pgvector
- Redis for cache/job/rate-limit support
- JSON request and audit logging without decrypted evidence

Core records include organizations, users, cases, assignments, participants, evidence, custody events, documents, immutable document versions, signatures, grants, audits, notifications, chunks, AI claims/sources, entities/relationships, timeline events, Merkle batches/leaves, anchors, verification tokens, and durable outbox events.

Swagger is available at <http://localhost:8000/docs>.

Important routes:

```text
POST /api/v1/auth/login
GET|POST /api/v1/cases
GET /api/v1/cases/{case_number}
GET /api/v1/cases/{case_number}/timeline
GET /api/v1/cases/{case_number}/graph
POST /api/v1/documents
POST /api/v1/documents/{id}/versions
GET /api/v1/documents/{id}/download
GET /api/v1/evidence/{id}/passport
POST /api/v1/evidence/{id}/custody
POST /api/v1/verification/document
POST /api/v1/ai/case/{case_number}/brief
POST /api/v1/ai/case/{case_number}/ask
POST /api/v1/access/grants
POST /api/v1/access/break-glass
POST /api/v1/blockchain/checkpoints
GET /api/v1/blockchain/merkle/{event_id}/proof
GET /api/v1/cases/{case_number}/verification-report
GET /api/v1/public/verify/{token}
GET /api/v1/health
```

## Authentication and Authorization

Local authentication uses Keycloak/OIDC. RS256/JWKS signatures, issuer, and client binding are verified. Role, organization, clearance, assignment, and account status remain authoritative in PostgreSQL rather than trusting role claims from the identity provider.

Roles:

```text
INVESTIGATING_OFFICER  SUPERVISOR  FSL_OFFICER  PROSECUTOR
COURT_USER  EXTERNAL_EXPERT  AUDITOR  ADMIN
```

Policy checks cover case assignment, organization, clearance, classification, evidence linkage, document relevance, temporary grants, expiry, and oversight scope. They run before document metadata/download, evidence passports, timeline/graph sources, search/vector retrieval, AI context, reports, and verification details.

Break-glass requires an authorized role, justification, requested scope, expiry, audit record, and supervisor-review flag. Production still requires Government IAM/PKI and authorization-code + PKCE or a BFF with secure HTTP-only cookies.

## Storage, Cryptography, and Files

MinIO is the default private vault. IPFS/Kubo is optional and receives ciphertext only. Plaintext sensitive evidence never belongs on public IPFS. Storage references/CIDs remain protected backend metadata and never go to the public chain.

Implemented controls:

- AES-256-GCM encryption
- random per-object DEK and nonce
- versioned wrapped-DEK envelopes
- no plaintext DEKs in PostgreSQL
- SHA-256 original and encrypted fingerprints
- Ed25519 service attestations
- immutable document versions and previous-hash chains
- exact duplicate detection
- modified-file `HASH_MISMATCH`
- PDF/TXT/JPG/PNG validation and upload bounds
- production fail-closed ClamAV boundary
- storage cleanup on SQL rollback

Local KEK wrapping is development-only. Production expects an approved NIC/government KMS or HSM gateway.

## Hyperledger Fabric

Fabric is the permissioned provenance ledger.

- channel: `justicechannel`
- chaincode: `nyayagraph`
- current local organizations: `PoliceMSP`, `FSLMSP`
- planned managed topology: PoliceMSP, FSLMSP, ProsecutionMSP, CourtMSP

Operations include case/document/evidence registration, immutable versions, custody transfer, access grant/revoke/record, checkpoints, and artifact verification.

Fabric stores hashes, commitments, versions, organization/actor references, timestamps, and previous hashes. It does not store PDFs, witness names, victim identities, FIR text, or complete case text.

If Fabric is unavailable, development provenance is visibly marked `dev-ledger-*`. `make fabric-sync` replays missing/fallback document fingerprints and saves only genuine transaction IDs. `make fabric-up` starts/reuses the network, deploys chaincode, restarts the API in Fabric mode, and synchronizes fallback records.

Latest live verification:

- 31/31 current document versions have genuine Fabric transaction IDs;
- 31/31 registered hashes verify directly through chaincode;
- two flagship custody events have genuine Fabric transactions.

## Public EVM and Merkle Anchoring

`CaseIntegrityAnchor` is a Solidity 0.8.24 contract. Supported modes are:

- real local Hardhat EVM, chain ID `31337`;
- Polygon Amoy, chain ID `80002`, with supplied RPC and funded testnet signer;
- explicit mock mode for isolated tests.

The current demo uses Hardhat. The latest local deployment confirmed address `0x5FbDB2315678afecb367f032d93F642f64180aa3`; it is not permanent and resets with local chain state.

Eligible provenance events are canonically serialized, hashed into Merkle leaves, built into a binary tree, stored as batches/leaves, recorded on Fabric, and anchored through the configured public provider. Only the Merkle root, non-sensitive batch key, metadata commitment, and timestamp are public. Case IDs, FIR numbers, identities, evidence types, storage paths, and CIDs are forbidden.

## AI, Retrieval, Contradictions, and Graph

Secure retrieval flow:

```text
case authorization → allowed document IDs/chunks → metadata + PostgreSQL FTS
+ pgvector semantic retrieval → rerank → evidence-delimited prompt → generation
→ claim validation → citation validation → output authorization
```

Evidence is untrusted prompt data. Instructions inside documents are never followed. The model cannot call privileged mutation tools. Supported factual claims require validated authorized sources. Unsupported/restricted questions return insufficient evidence.

The default MVP supports deterministic demo intelligence. Approved OpenAI-compatible LLM and 384-dimensional embedding HTTP providers can be configured without changing authorization/citation validation.

Contradictions are detected by normalized structured facts first; the system reports time/location/identity/vehicle/sequence discrepancies without deciding truthfulness. PostgreSQL entity/relationship tables power the graph. Neo4j is optional and disabled.

## Fictional Dataset

The seed contains:

- 18 fictional mock cases
- 31 encrypted documents
- 35 evidence records
- more than ten case types
- five workflow states

The flagship case `MH-PUNE-2026-00142` includes 14 documents, 18 evidence records, a vehicle-theft/resale scenario, FIR, three witness statements, two CCTV reports, forensic report, photographs, mobile/call-detail summaries, seizure memo, charge sheet, and court order.

Intentional flagship issues:

- Witness-01 reports 21:20;
- Witness-03 reports approximately 22:05;
- CCTV reports 21:27;
- Witness-03 is restricted from the External Expert;
- FSL material references missing Exhibit E-07;
- E-12 has a 3h22m custody anomaly;
- a modified forensic file produces `HASH_MISMATCH`.

The other 17 cases cover cyber fraud, narcotics, burglary, missing-person workflow, document fraud, arms recovery, financial fraud, assault, vehicle theft, cyber extortion, warehouse theft, identity theft, organized-crime inquiry, arson, organized handset theft, and court-compliance closure.

Each additional case has a real application path: case/assignment, evidence, AES-GCM encrypted private-vault document, original/encrypted hashes, wrapped DEK, signature, authorized search chunk, and configured-ledger provenance. Every description/artifact says it is fictional and not government data.

## Demo Identities

All development identities use password `NyayaDemo!2026`:

| Email | Role |
|---|---|
| `io@nyaya.local` | Investigating Officer |
| `fsl@nyaya.local` | FSL Officer |
| `expert@nyaya.local` | External Expert |
| `auditor@nyaya.local` | Auditor |

These credentials are local-demo only and must never be reused in production.

## Commands and URLs

```bash
cp .env.example .env
make up
make migrate
make seed
make ipfs-up
make fabric-up
make blockchain-deploy
make demo
make test
make security-test
```

Maintenance: `make logs`, `make fabric-sync`, `make demo-reset`, `make backup`, `make restore BACKUP=...`, `make retention`, `make outbox`, `make production-check`, and `make down`.

| Service | URL |
|---|---|
| Frontend | <http://localhost:3000> |
| API | <http://localhost:8000> |
| Swagger | <http://localhost:8000/docs> |
| Keycloak | <http://localhost:8080> |
| MinIO console | <http://localhost:9001> |
| IPFS API | <http://localhost:5001> |
| Hardhat RPC | <http://localhost:8545> |

## Verified State

- 43 backend/domain/security tests pass.
- All 18 cases open through the authenticated live API.
- All 31 current document hashes and signatures pass workspace verification.
- All 31 document hashes pass direct Fabric verification.
- Five Solidity tests pass.
- Fabric Go tests and `go vet` pass.
- Frontend ESLint, TypeScript, and production build pass.
- Bandit passes.
- `pip-audit` reports no known Python dependency vulnerabilities.
- Production Compose validation passes.
- GitHub launch-readiness CI passes on `main`.
- Dependabot monitors Python, npm, Go, and GitHub Actions weekly.

Latest full local health:

```json
{"api":"ok","database":"ok","postgres":"ok","redis":"ok","minio":"ok","ipfs":"ok","neo4j":"disabled","fabric":"ok","publicChain":"hardhat"}
```

## Failure Behavior

- Fabric offline: SQL persists and provenance is marked fallback/pending; later synchronize.
- Public anchor offline: private provenance remains verified; external checkpoint stays pending.
- IPFS offline: MinIO remains the default vault.
- Neo4j offline: PostgreSQL graph continues.
- LLM offline: metadata, hashes, evidence, custody, integrity, timeline, graph, verification, and deterministic demo output remain available.
- Optional health may be `disabled` or `unavailable` without collapsing the API.

Fallbacks must never be shown as genuine external success.

## Remaining Production Work

1. Government IAM/PKI and secure browser session flow.
2. Approved NIC/government KMS/HSM and key-lifecycle validation.
3. Managed four-organization Fabric and committed-after-timeout reconciliation.
4. Polygon Amoy deployment if external anchoring is required.
5. Shared Redis-backed rate limiting.
6. OCR for scanned PDFs/images.
7. Full browser E2E automation for the complete role/access/tamper demo.
8. Production TLS ingress/domain, encrypted coherent backups, restore drills, monitoring, alerting, retention, and runbooks.
9. Independent penetration test and deployment hardening.
10. Measured Neo4j adoption decision.

Government connectors and real-record import are out of the current mock-data scope. They require specifications, credentials, legal authorization, and data-sharing approval. Remaining work is tracked in GitHub Issues.

## Engineering Principles

```text
correctness → security → working demo → simplicity → testability → explainability → scale
```

- Encryption protects confidentiality.
- RBAC/ABAC protects authorization.
- Signatures protect authenticity.
- Hashes protect integrity.
- Fabric protects shared provenance.
- Merkle anchors provide external tamper evidence.
- Secure RAG provides evidence-grounded intelligence.
- Evidence files never belong on a blockchain.
- Confidential metadata never belongs on a public chain.
- Existing systems are integrated only when authorized, not replaced.
- Mock/local behavior is labelled truthfully.

Update this file when project-wide context changes. Update `DECISIONS.md` for decisions, `FLOW.md` for call paths, and `STATUS.md` for delivery state. Never put production secrets in documentation.
