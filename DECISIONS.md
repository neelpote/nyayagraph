# NyayaGraph Engineering Decisions

## DEC-0001 — Use PostgreSQL with an optional pgvector extension for the MVP

**Date:** 2026-09-02  
**Status:** Accepted

### Context
NyayaGraph needs a transactional case database and authorization-filtered semantic retrieval.

### Decision
Use PostgreSQL as the authoritative store and pgvector when semantic indexing is enabled; do not add a dedicated vector database by default.

### Why
- fewer operational services;
- access filters remain colocated with retrieval;
- the expected demonstration dataset is small.

### Alternatives Considered
- Qdrant;
- Milvus;
- Elasticsearch vector search.

### Tradeoffs
This simplifies local setup, while dedicated vector stores may be preferable at national production scale.

### Consequences
The default stack has no Qdrant service. Revisit when measured retrieval scale or latency requires independent vector scaling.

## DEC-0002 — Establish a secure development-ledger fallback before Fabric

**Date:** 2026-09-02  
**Status:** Temporary

### Context
A Fabric network is valuable for cross-organization provenance but can prevent a 36-hour demo from starting reliably.

### Decision
Use a `ProvenanceLedger` interface with `DatabaseDevLedger` as the default when `FABRIC_ENABLED=false`; Fabric remains an explicit adapter target.

### Why
- enables an end-to-end verified workflow locally;
- avoids pretending a ledger transaction occurred;
- keeps the UI and audit design independent of Fabric availability.

### Alternatives Considered
- make Fabric mandatory at startup;
- omit provenance until Fabric is available.

### Tradeoffs
The fallback cannot provide multi-organization consensus, so responses must identify it as development-ledger state.

### Consequences
The first demo slice has working provenance records without a running Fabric peer.

### Revisit Before
SIH final deployment or any multi-organization trial.

## DEC-0003 — Encrypt evidence before private-object storage

**Date:** 2026-09-02  
**Status:** Accepted

### Context
Evidence files must remain confidential even if object-store access is misconfigured.

### Decision
Compute the original SHA-256, encrypt bytes with AES-256-GCM, store only encrypted bytes, and record both original and encrypted hashes.

### Why
- supports integrity verification of both the supplied and stored artifacts;
- prevents plaintext evidence from residing in MinIO;
- provides a clear Evidence Passport.

### Alternatives Considered
- MinIO server-side encryption only;
- unencrypted storage in development.

### Tradeoffs
Application-managed encryption requires key-management discipline. A local KEK wrapper is development-only.

### Consequences
Plaintext DEKs are never persisted. Replace the KEK wrapper with a government KMS/HSM before production.

## DEC-0004 — Pin the PostgreSQL development driver to a Python-3.13-compatible patch release

**Date:** 2026-09-02  
**Status:** Accepted

### Context
The initial `psycopg2-binary` pin did not provide a usable local wheel for the host Python interpreter and attempted a source build requiring `pg_config`.

### Decision
Use `psycopg2-binary==2.9.11` for the FastAPI service.

### Why
- retains the existing SQLAlchemy URL and Docker configuration;
- enables supported local Python installations without system PostgreSQL build tools.

### Alternatives Considered
- require local PostgreSQL build tooling;
- migrate immediately to psycopg v3.

### Tradeoffs
This remains a conventional development driver; production driver and connection policy should be validated in the target government environment.

### Consequences
Local test setup should use a wheel rather than compile the driver.

## DEC-0005 — Authorize the parent document before tamper verification

**Date:** 2026-09-02  
**Status:** Accepted

### Context
The verification endpoint accepts a document-version identifier and can return the registered fingerprint. Without a parent-document check, an authenticated user could probe versions outside their authorized scope.

### Decision
Resolve the immutable version, load its parent document, and apply the same RBAC/ABAC read policy before hashing or returning comparison details.

### Why
- prevents insecure direct-object reference and fingerprint disclosure;
- keeps verification aligned with document retrieval policy;
- preserves the rule that authorization precedes evidence operations.

### Alternatives Considered
- expose hash verification publicly;
- return only a boolean without authorization.

### Tradeoffs
Public court verification will require a separate opaque QR-token endpoint that reveals only non-confidential authenticity state.

### Consequences
The authenticated verification route cannot be used to enumerate protected document fingerprints.

## DEC-0006 — Use deterministic local Merkle checkpoints behind a public-anchor provider

**Date:** 2026-09-02  
**Status:** Temporary

### Context
Merkle proofs must be testable before an EVM node or Polygon Amoy endpoint is available.

### Decision
Canonicalize provenance events, persist Merkle batches and proofs in PostgreSQL, and use an explicitly labelled `LocalDevAnchorProvider` until the Hardhat adapter is connected.

### Why
- the hashing and proof logic can be tested independently;
- no simulated transaction is presented as a public blockchain transaction;
- the provider boundary keeps the checkpoint workflow stable.

### Alternatives Considered
- block Merkle work until Hardhat is running;
- claim a deterministic mock hash is an EVM transaction.

### Tradeoffs
Local checkpoints provide reproducible proof validation but no external consensus or timestamp assurance.

### Consequences
Responses use `VERIFIED_LOCAL` and `LOCAL_DEV`; the UI must continue to say external checkpoint pending.

### Revisit Before
The blockchain demonstration milestone.

## DEC-0007 — Model document changes as immutable hash-linked versions

**Date:** 2026-09-02  
**Status:** Accepted

### Context
Corrections and additions must remain attributable without overwriting registered evidence.

### Decision
Store each change as a new encrypted object and `DocumentVersion`; link it to the immediately preceding version using `previous_version_hash` and create a provenance event.

### Why
- preserves all prior evidence bytes and fingerprints;
- makes version-chain verification deterministic;
- creates an auditable reason and actor boundary for each change.

### Alternatives Considered
- overwrite the current object;
- retain versions only through object-store history.

### Tradeoffs
Immutable versions consume additional storage, which is appropriate for evidentiary records.

### Consequences
The API exposes `POST /documents/{id}/versions`; identical bytes are rejected rather than creating meaningless versions.

## DEC-0008 — Use Fabric for private provenance and an EVM chain only for aggregate checkpoints

**Date:** 2026-09-02  
**Status:** Accepted

### Context
Evidence provenance is shared by police, FSL, prosecution and court organizations, while public verification must not expose case metadata.

### Decision
Use Hyperledger Fabric on one `justicechannel` for artifact and custody provenance. Anchor only Merkle roots and metadata commitments to local Hardhat by default, with Polygon Amoy as an optional provider.

### Why
Fabric supplies organization-scoped identity and shared history; the EVM checkpoint supplies external tamper evidence without publishing case identifiers.

### Alternatives Considered
- public-chain evidence records;
- one Fabric channel per case;
- database signatures only.

### Tradeoffs
Fabric adds operational setup. The resilient adapter records a visibly pending database-ledger event when a peer is unavailable.

### Consequences
No evidence bytes, names, FIR numbers, storage references or CIDs are written to a public chain.

## DEC-0009 — Keep AI deterministic and authorization-first for the MVP

**Date:** 2026-09-02  
**Status:** Accepted

### Context
The demo must work without an external LLM and must prove that restricted evidence never enters AI context.

### Decision
Resolve authorized document IDs before retrieval, use stored/seed-bound chunks, deterministic contradiction extraction, claim validation and exact source citations. Keep the provider boundary for a later local or API-compatible LLM.

### Why
- reliable offline demo;
- inspectable citations;
- no autonomous actions;
- access grants immediately affect retrieval.

### Alternatives Considered
- unrestricted vector retrieval followed by output filtering;
- mandatory hosted LLM;
- free-form autonomous agent.

### Tradeoffs
Language quality is intentionally simpler than a production model, but all factual output is attributable.

### Consequences
AI output is read-only and never determines guilt.

## DEC-0010 — Use hashed demo passwords and persisted random development keys

**Date:** 2026-09-02  
**Status:** Accepted

### Context
Predictable JWT and encryption keys would make even a demo unsafe, while local startup must remain simple.

### Decision
Hash seeded passwords with PBKDF2-HMAC-SHA256, require strong configured keys outside development, and generate a mode-0600 development KEK file when none is supplied.

### Alternatives Considered
- plaintext demo passwords in the database;
- hardcoded JWT/KEK values;
- mandatory external KMS for local development.

### Tradeoffs
The development KEK is host-local and is not suitable for multi-node production.

### Consequences
Production deployment must supply secrets and replace local wrapping with NIC/government KMS/HSM integration.

## DEC-0011 — Freeze the Alembic baseline and model pgvector explicitly

**Date:** 2026-09-02  
**Status:** Accepted

### Context
A migration that calls current SQLAlchemy metadata changes historical behavior and cannot evolve an installed database safely.

### Decision
Generate a static Alembic baseline containing explicit tables, constraints and indexes; create the PostgreSQL `vector` extension and use a 384-dimensional pgvector column with a JSON SQLite test variant.

### Alternatives Considered
- dynamic `Base.metadata.create_all()` migration;
- schema creation only at application startup.

### Tradeoffs
Schema changes now require new monotonic migrations, adding a small maintenance step.

### Consequences
Fresh and migrated installations are reviewable and reproducible.

## DEC-0012 — Use selectable-text extraction before OCR

**Date:** 2026-09-02  
**Status:** Accepted

### Context
Most demo PDFs and TXT records do not require expensive OCR.

### Decision
Validate PDFs with PyMuPDF, extract selectable text first, chunk by page, and persist source hashes and classification. Keep OCR as a provider extension for scanned documents.

### Alternatives Considered
- OCR every upload;
- store only seeded text;
- delay indexing until a background-worker stack exists.

### Tradeoffs
Scanned images remain metadata-searchable until an OCR provider is enabled.

### Consequences
The synchronous MVP ingestion path remains understandable and newly uploaded text is immediately retrievable.

## DEC-0013 — Apply process-local rate limits in the single-replica MVP

**Date:** 2026-09-02  
**Status:** Temporary

### Context
AI and search endpoints need abuse protection, but adding a distributed limiter is unnecessary for the single API replica.

### Decision
Rate-limit hashed session identities in memory, with a stricter AI/search budget, and emit a request ID plus structured request metadata.

### Alternatives Considered
- no rate limiting;
- Redis-backed limiter immediately.

### Tradeoffs
Limits are not shared between replicas and reset on restart.

### Consequences
Move limiter state to Redis before horizontal scaling.

### Revisit Before
Any deployment with more than one API replica.

## DEC-0014 — Upgrade the web runtime to the current stable Next.js line

**Date:** 2026-09-02  
**Status:** Accepted

### Context
The initial scaffold used Next.js 14.2.16, which was no longer the stable/security-supported target during implementation.

### Decision
Upgrade to Next.js 16.3.4 with React 19.2.8, the flat ESLint configuration and patched PostCSS 8.5.26.

### Why
- satisfies the latest-stable requirement;
- removes production dependency audit findings;
- keeps the App Router on an actively supported release.

### Alternatives Considered
- remain on the old scaffold;
- upgrade only to the 14.x backport line.

### Tradeoffs
The major upgrade required the newer lint configuration and build verification.

### Consequences
Node.js 20 is the supported container runtime and the production dependency audit reports no known vulnerabilities at build time.

## DEC-0015 — Hydrate browser sessions before rendering protected UI

**Date:** 2026-09-02  
**Status:** Accepted

### Context
Next.js server rendering cannot read the development session stored in browser storage. Reading it in the initial client render produced different server/client trees and a hydration error. Next.js 16 also exposes dynamic route parameters asynchronously.

### Decision
Render the same loading boundary on server and initial client render, load the session in an effect, and redirect only after hydration. Await server-component route parameters and unwrap client-component parameters with React `use()`.

### Alternatives Considered
- disable server rendering for all protected pages;
- move the development token into a non-HttpOnly cookie;
- ignore the development-only hydration warning.

### Tradeoffs
Protected pages briefly display a neutral loading state. Production IAM should replace browser storage with a secure server-readable session.

### Consequences
Dynamic case and evidence routes work on Next.js 16 without undefined identifiers or hydration mismatch errors.

### Related Files
- `apps/web/components/app-shell.tsx`
- `apps/web/app/cases/[caseId]/page.tsx`
- `apps/web/app/evidence/[evidenceId]/page.tsx`

## DEC-0016 — Upgrade Python security-sensitive dependencies after vulnerability audit

**Date:** 2026-09-02  
**Status:** Accepted

### Context
The final dependency audit identified advisories affecting the original FastAPI/Starlette, JWT and cryptography pins.

### Decision
Standardize supported development/runtime Python on 3.12 (matching the API container), upgrade FastAPI to 0.141.1, multipart parsing to 0.0.32, PyJWT to 2.13.0, cryptography to 50.0.1, Pillow to 12.3.0, and the test runtime to pytest 9.1.1, then rerun the full regression and dependency audits.

### Alternatives Considered
- retain the original known-working pins;
- suppress vulnerability identifiers without upgrading;
- unpin all dependencies.

### Tradeoffs
The project keeps exact reproducible pins, requires Python 3.12+, and must periodically repeat dependency review.

### Consequences
Available security fixes are incorporated without weakening reproducibility or skipping the application test suite.

## DEC-0017 — Derive workspace intelligence from persisted authorized records

**Date:** 2026-09-02  
**Status:** Accepted

### Context
Static case, graph, integrity and AI constants could disagree with stored evidence and authorization.

### Decision
Build workspace responses from PostgreSQL and authorized `DocumentChunk` rows. Seed text passes through the same encrypted storage and models as uploads.

### Alternatives Considered
- frontend fallback records;
- fixed demonstration responses;
- unrestricted AI context.

### Tradeoffs
The optional seed remains explicitly synthetic because no authorized government source is available; runtime responses are data-driven.

### Consequences
Replacing records changes every screen naturally, and unauthorized chunks never enter AI context.

## DEC-0018 — Keep MinIO authoritative and make encrypted IPFS opt-in

**Date:** 2026-09-02  
**Status:** Accepted

### Context
Confidential evidence needs reliable private storage, while IPFS was requested as an optional encrypted tier.

### Decision
Default to MinIO. With explicit IPFS configuration, send only AES-256-GCM ciphertext to Kubo and retain the protected CID reference.

### Alternatives Considered
- plaintext IPFS;
- public CID anchoring;
- mandatory IPFS.

### Tradeoffs
Operators manage private IPFS pinning separately; MinIO is the simpler default.

### Consequences
Storage selection is deterministic and provider failures never silently change tiers.

## DEC-0019 — Bind Fabric authorization to signed MSP identity

**Date:** 2026-09-02  
**Status:** Accepted

### Context
An organization argument is spoofable and cannot authorize ledger writes.

### Decision
Derive the invoker MSP from Fabric client identity, enforce operation allowlists, ignore claimed organization arguments, and request endorsements from configured peers. The API image includes the pinned Fabric 2.5.16 peer client and mounts MSP material read-only.

### Alternatives Considered
- trust organization arguments;
- present a database ledger as Fabric;
- accept generic development MSP aliases in production chaincode.

### Tradeoffs
The local network maps two organizations to `PoliceMSP` and `FSLMSP`; production still needs the four-organization topology.

### Consequences
Live API writes receive real Fabric transaction IDs; unavailable networks remain visibly pending.

## DEC-0020 — Use a UUID-derived public checkpoint identifier

**Date:** 2026-09-02  
**Status:** Accepted

### Context
Display sequences restart after a demo reset, but the EVM contract rejects reused keys permanently.

### Decision
Keep the small display sequence and derive the contract `uint256` key from the non-sensitive Merkle batch UUID.

### Alternatives Considered
- reuse display sequences;
- redeploy after every reset;
- expose case identifiers.

### Tradeoffs
The contract key differs from the displayed sequence.

### Consequences
Checkpoint creation is collision-resistant across resets without leaking case metadata.

## DEC-0021 — Use Hardhat 3 with a minimal plugin set

**Date:** 2026-09-02  
**Status:** Accepted

### Context
The prior toolbox tree contained avoidable advisories and Hardhat 3 requires Node.js 22.

### Decision
Use Hardhat 3.15, Node.js 22, ethers and the Mocha plugin only.

### Alternatives Considered
- retain Hardhat 2;
- full toolbox;
- mock the EVM.

### Tradeoffs
Deployment and tests use the Hardhat 3 network API.

### Consequences
Contract deployment and tests run with zero reported npm vulnerabilities.

## DEC-0022 — Use one responsive evidence-desk shell and Lucide navigation icons

**Date:** 2026-09-03  
**Status:** Accepted

### Context
The working frontend used inconsistent Unicode symbols, lost primary navigation on small screens, and the AI page displayed a status-only workspace placeholder instead of requesting its authorized brief.

### Decision
Keep the existing server-driven pages, refine the shared CSS shell for desktop and mobile, use `lucide-react` for accessible consistent navigation, and load the authorized AI brief from its existing API on page entry.

### Why
- fixes every application page through one shared shell;
- restores mobile navigation without a custom menu dependency;
- makes citations readable and actionable;
- reuses existing backend contracts instead of adding state infrastructure.

### Alternatives Considered
- a full component-library rewrite;
- retaining text glyph icons;
- duplicating the case brief inside the workspace response.

### Tradeoffs
The global stylesheet remains the MVP design system; a future design system may split it into scoped modules as the frontend grows.

### Consequences
The interface has consistent icons, visible keyboard focus, reduced-motion support, responsive layouts, and real authorized AI content on first load.

### Related Files
- `apps/web/components/app-shell.tsx`
- `apps/web/app/ai/page.tsx`
- `apps/web/components/case-workspace.tsx`
- `apps/web/app/globals.css`

## DEC-0023 — Verify external OIDC identity and resolve authorization locally

**Date:** 2026-09-03  
**Status:** Accepted

### Context
Development JWTs cannot represent a production government identity boundary.

### Decision
Support Keycloak or another standards-compatible OIDC issuer, verify RS256/JWKS issuer and client binding, then resolve the subject to an active local user. Organization, role and clearance remain authoritative in PostgreSQL. Retain `dev_jwt` only as an explicit development mode.

### Alternatives Considered
- trust roles embedded in identity-provider tokens;
- keep application-issued JWTs in production;
- implement a provider-specific government IAM protocol without supplied specifications.

### Tradeoffs
The local realm uses a password exchange for demo usability; production must use authorization-code + PKCE/BFF cookies and approved IAM federation.

### Consequences
Keycloak-backed login is live-testable locally without granting token claims direct evidence permissions.

## DEC-0024 — Store versioned KMS envelopes instead of raw wrapped keys

**Date:** 2026-09-03  
**Status:** Accepted

### Context
Evidence encrypted under an older KMS key must remain decryptable after rotation.

### Decision
Store `{v, provider, keyId, wrapped}` as the wrapped-DEK value. Local KEK use is rejected outside development; production calls an approved HTTPS NIC KMS/HSM gateway.

### Alternatives Considered
- store only opaque ciphertext;
- store plaintext DEKs;
- bind all historical evidence to the current key ID.

### Tradeoffs
The KMS must retain or migrate historical keys. The database learns a non-secret provider/key identifier.

### Consequences
Raw DEKs never enter PostgreSQL and key rotation no longer silently makes older evidence unreadable.

## DEC-0025 — Use configurable grounded LLM and embedding HTTP providers

**Date:** 2026-09-03  
**Status:** Accepted

### Context
The deterministic demo path must not be mistaken for a configured AI model, while deployments may use local or approved hosted models.

### Decision
Use an OpenAI-compatible HTTP boundary for structured generation and 384-dimensional embeddings. Retrieval is authorization-filtered before provider calls, generated chunk IDs are allowlisted, and unsupported claims are rejected. Keep deterministic mode explicitly labelled `demo`.

### Alternatives Considered
- hardcode one commercial provider;
- let the model query the database directly;
- add a separate vector database.

### Tradeoffs
Operators must supply a compatible endpoint/model and availability policy; pgvector dimension is fixed for this MVP.

### Consequences
Real models can be enabled without changing case authorization or citation validation.

## DEC-0026 — Scope oversight access and share one evidence policy

**Date:** 2026-09-03  
**Status:** Accepted

### Context
Role-only supervisor/auditor shortcuts and endpoint-specific evidence checks could disclose data across organizations.

### Decision
Only ADMIN is global. Supervisors and auditors are organization-scoped; auditors do not implicitly download evidence. All workspace, timeline, graph, report, passport and AI paths call the same evidence authorization policy.

### Alternatives Considered
- global oversight roles;
- duplicate endpoint filters;
- clearance-only evidence access.

### Consequences
Restricted evidence cannot leak through alternate metadata or AI paths, and negative cross-organization tests are required.

## DEC-0027 — Queue production Fabric writes in a transactional outbox

**Date:** 2026-09-03  
**Status:** Accepted

### Context
Submitting an irreversible ledger transaction before the SQL case transaction commits can leave inconsistent systems when the database fails.

### Decision
Production records provider work in `outbox_events` within the domain transaction. A separate worker uses locked batches and bounded exponential retry; development may submit synchronously for demonstration feedback. Newly stored objects are tracked and deleted on SQL rollback.

### Alternatives Considered
- call Fabric before SQL commit;
- silently retry only in process memory;
- introduce Kafka/Celery.

### Tradeoffs
Production UI can temporarily show ledger synchronization pending. Committed-after-timeout reconciliation remains an operator hardening gate for a managed Fabric deployment.

### Consequences
Database state and retry intent commit atomically without adding a message broker.

## DEC-0028 — Fail closed on production malware scanning

**Date:** 2026-09-03  
**Status:** Accepted

### Context
File structure checks do not detect malicious document content.

### Decision
Add a ClamAV INSTREAM boundary before parsing/encryption and reject production uploads when the scanner is disabled, misconfigured, unavailable or indeterminate.

### Alternatives Considered
- rely only on MIME/PDF/image checks;
- bundle antivirus signatures into the API image;
- accept and scan after evidence release.

### Consequences
Production deployment must provide a managed scanner and ingress body limit; development can explicitly run without it.

## DEC-0029 — Gate every change with one minimal launch-readiness workflow

**Date:** 2026-09-04
**Status:** Accepted

### Context
The repository had local test commands but no required, repeatable validation on pushes or pull requests.

### Decision
Use one GitHub Actions workflow with independent API, web, public-anchor, Fabric-chaincode and production-configuration jobs. Enable weekly dependency updates for each package ecosystem.

### Why
- failures are isolated by subsystem;
- Python 3.12 is enforced consistently;
- security and dependency scans run without publishing secrets;
- the production Compose overlay is proven syntactically complete with non-secret placeholder values.

### Alternatives Considered
- rely on local developer checks;
- introduce a separate CI platform;
- build and start the complete multi-ledger stack on every pull request.

### Tradeoffs
The workflow does not provision a four-organization Fabric network or external IAM/KMS/government services. Those require dedicated integration environments.

### Consequences
Routine regressions are blocked early, while external launch gates remain explicitly tracked as GitHub issues. Node jobs pin npm 11.6.2 for deterministic lockfile installation. JavaScript vulnerability monitoring uses weekly Dependabot updates because the npm audit endpoint proved slow and non-deterministic on both local and GitHub runners; Python auditing remains an in-workflow blocking check.

### Related Files
- `.github/workflows/ci.yml`
- `.github/dependabot.yml`
- `Makefile`

### Related Decisions
- DEC-0027
- DEC-0028

## DEC-0032 — Add local Qwen3-8B through Ollama behind the secure RAG boundary

**Date:** 2026-09-06
**Status:** Accepted

### Context
The MVP had deterministic evidence-grounded output and a generic OpenAI-compatible path, but no tested local model integration.

### Decision
Support `LLM_PROVIDER=ollama` with Qwen3-8B as the recommended local model while retaining deterministic demo mode and the OpenAI-compatible provider. Authorization filters chunks before model invocation, and returned claims pass citation and faithfulness validation.

### Alternatives Considered
- keep deterministic output only;
- require a hosted proprietary model;
- run a model inside the API container.

### Tradeoffs
Ollama keeps evidence local and is simple to operate, but Qwen3-8B needs several gigabytes of storage and suitable host memory. Demo mode remains the reliable fallback.

### Consequences
The API exposes `/api/v1/health/llm`, Docker can reach host Ollama through `host.docker.internal`, and the AI UI shows generation and evidence-support states. Unrelated line-ending and vendor rewrites from the source branch were excluded during integration.

### Related Files
- `apps/api/app/ai/llm/`
- `apps/api/app/ai/providers.py`
- `apps/api/app/ai/case_agent.py`
- `apps/api/tests/test_llm_integration.py`
- `apps/web/app/ai/page.tsx`

## DEC-0030 — Keep unit and API tests independent of infrastructure

**Date:** 2026-09-04
**Status:** Accepted

### Context
The API suite inherited the default MinIO backend and failed when run in clean CI without a live object store.

### Decision
Set explicit test-only provider modes in `tests/conftest.py` before application imports. Dedicated integration and deployment checks remain responsible for real provider connectivity.

### Alternatives Considered
- start the entire Docker stack for every API test;
- let tests inherit developer environment variables;
- mock each MinIO call separately.

### Tradeoffs
The fast API suite validates provider boundaries and local encrypted storage, while live MinIO/IPFS/Fabric behavior requires its separate integration path.

### Consequences
API tests are deterministic on Python 3.12 and cannot accidentally write to developer or production infrastructure.

### Related Files
- `apps/api/tests/conftest.py`
- `.github/workflows/ci.yml`

## DEC-0031 — Use one deep flagship case plus 17 compact end-to-end mock cases

**Date:** 2026-09-04
**Status:** Accepted

### Context
Government case access is not available for the hackathon, but the UI, authorization rules and storage/provenance paths need enough varied data to expose dataset-level defects.

### Decision
Seed 18 explicitly fictional cases. Keep `MH-PUNE-2026-00142` as the deep demonstration with contradictions, restricted evidence and custody anomalies. Give each of the other 17 cases at least one real application artifact: an evidence record, encrypted stored document, two SHA-256 fingerprints, wrapped key, signature, searchable chunk and configured-ledger registration.

### Why
- provides useful breadth without duplicating hundreds of heavy demo artifacts;
- exercises the real secure ingestion outputs rather than decorative rows;
- keeps seeding and the full test suite fast enough for SIH iteration;
- makes the absence of authorized government data unambiguous.

### Alternatives Considered
- fabricate government-looking production records;
- duplicate the full flagship dataset 18 times;
- create metadata-only case rows.

### Tradeoffs
The additional cases are intentionally shallower than the flagship and do not each contain a unique contradiction or custody anomaly. They do exercise case loading, policy, storage integrity, signature verification, search indexing and provenance boundaries.

### Consequences
Mock data is the supported MVP dataset. Any future authorized importer remains a separate integration project and must not silently reuse the seed path. Because developers may seed before starting Fabric, `make fabric-up` runs an explicit synchronization pass that replaces only fallback document references and refuses to fabricate transaction IDs.

The Fabric startup wrapper reuses an existing active `justicechannel` instead of trying to join peers twice, and explicitly exposes the official Fabric binaries before its post-deployment verification.

Local EVM deployment refreshes its locked dependency volume before invoking Hardhat so a Docker restart cannot reuse an incomplete or stale `node_modules` tree.

### Related Files
- `apps/api/app/seed.py`
- `apps/api/app/sync_fabric.py`
- `blockchain/fabric/scripts/fabric-up.sh`
- `blockchain/fabric/scripts/fabric-deploy-chaincode.sh`
- `apps/api/tests/test_demo_flow.py`
- `README.md`
