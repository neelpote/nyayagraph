# NyayaGraph Execution Flow

This document maps runtime execution paths across frontend, backend, storage, provenance and infrastructure.

Last Updated: 2026-09-04

## FLOW-000 ? Fictional dataset bootstrap

1. `apps/api/app/seed.py::run()` creates the two demo organizations and four role identities, then builds the rich flagship case `MH-PUNE-2026-00142`.
2. `seed_additional_mock_cases()` creates 17 compact fictional cases covering varied jurisdictions, case types, classifications and workflow states.
3. Each additional case receives an IO assignment, evidence record, AES-256-GCM encrypted document, wrapped DEK, original/encrypted SHA-256 fingerprints, Ed25519 signature, authorized search chunk and provenance registration through the configured `ProvenanceLedger`.
4. A repeat seed adds only missing mock cases. `--reset` recreates the full dataset.
5. `apps/api/tests/test_demo_flow.py::test_all_18_fictional_cases_have_verified_real_artifacts()` opens every case through the API and verifies its current stored hash and signature state.

**Truthfulness boundary:** all generated descriptions and artifacts identify themselves as fictional. The seed never claims to contain live government records, and ledger mode remains `DATABASE_DEV` unless a successful Fabric submission returns a genuine transaction ID.

If seeding occurs while Fabric is offline, `make fabric-up` finishes by calling `apps/api/app/sync_fabric.py::run()`. It selects only missing or `dev-ledger-*` document references, submits each stored fingerprint through `FabricProvenanceLedger`, persists only genuine transaction IDs, and fails visibly if Fabric still cannot accept the records.

## FLOW-001 ? Identity-provider login

**Trigger:** `apps/web/app/login/page.tsx` submits credentials to the configured identity mode.

Selecting a development identity fills its email and the shared development password locally; it does not submit the form. The user explicitly presses **Access workspace** to begin authentication.

1. `apps/web/lib/api.ts` calls `POST /api/v1/auth/login`.
2. In Keycloak/OIDC mode, `apps/api/app/routers/auth.py::_keycloak_login()` exchanges the credentials with the configured realm; development mode can instead verify the seeded PBKDF2 password.
3. `apps/api/app/security/auth.py::decode_oidc_token()` verifies the RS256 signature, issuer and `aud`/`azp` client binding using the provider JWKS.
4. The OIDC `sub` resolves a local active user. Organization, role and clearance always come from PostgreSQL, never token-controlled role claims.
5. The browser retains the short-lived token in tab-scoped session storage and redirects to the case workspace.

On protected pages, `apps/web/components/app-shell.tsx::AppShell()` renders a stable loading boundary, restores the development session after hydration, and redirects unauthenticated users to `/login`. Dynamic server routes await Next.js route parameters before constructing API requests.

**Failure path:** invalid provider credentials/token receive `401`; disabled or unmapped users receive `403`. Government production deployment must replace the MVP password exchange with authorization-code + PKCE/BFF cookies.

## FLOW-002 ? Case-ID query

1. `apps/web/app/cases/[caseId]/page.tsx` requests `GET /api/v1/cases/{case_number}`.
2. `apps/api/app/routers/cases.py::get_case()` resolves `current_user` using `apps/api/app/security/auth.py::get_current_user()`.
3. `apps/api/app/services/case_service.py::CaseService.workspace()` calls `CaseRepository.by_number()` and `IntegrityService.case_integrity()`.
4. The response is filtered through `PolicyEngine.can_view_case()` and includes only authorized document metadata.

## FLOW-003 ? Document ingestion

`DocumentService.ingest_document(file, case_id, actor, metadata) -> DocumentVersion`

1. `apps/api/app/routers/documents.py::upload_document()` accepts the multipart upload after `PolicyEngine.can_upload()`.
2. `apps/api/app/services/document_service.py::DocumentService.ingest_document()` performs a bounded read, structural limits and `security/malware.py::MalwareScanner.scan()` before hashing or parsing, then checks exact duplicates.
3. `apps/api/app/security/encryption.py::EncryptionService.encrypt()` creates AES-256-GCM ciphertext and a versioned wrapped-DEK envelope containing its KMS provider/key identifier.
4. `apps/api/app/storage/providers.py` selects the explicitly configured MinIO, private IPFS or local provider and writes only encrypted bytes. Provider failures never silently change tiers.
5. SQLAlchemy persists `Document` and `DocumentVersion`; `apps/api/app/ai/ingestion.py::TextExtractionService.extract()` creates authorized `DocumentChunk` rows for selectable PDF/TXT text.
6. `apps/api/app/security/signatures.py::SignatureService.sign_version()` creates an Ed25519 signature.
7. Development may submit synchronously. Production writes `OutboxEvent` atomically with the domain transaction; `services/outbox_service.py::OutboxService.process()` later submits to Fabric with retry/backoff and persists the genuine transaction ID.
8. The API returns immutable fingerprints, actual storage backend and provenance reference.

**Failure paths:** invalid MIME/size/structure or malware returns `422`; unavailable mandatory scanner/storage returns `503`; duplicate bytes return `409`. A SQL rollback triggers `storage/transactional.py` to delete the newly written encrypted object.

### Immutable version creation

1. `POST /api/v1/documents/{document_id}/versions` applies both upload permission and parent-document read policy.
2. `DocumentService.create_version()` loads the current immutable version and rejects identical content.
3. New bytes are hashed, encrypted with a fresh DEK/nonce, and stored under a new `v{number}.bin` object key.
4. `DocumentVersion.previous_version_hash` links V2 to V1 without overwriting either record.
5. `DatabaseDevLedger.create_version()` records a `CREATE_VERSION` provenance event for later Merkle batching.

## FLOW-004 ? Tamper verification

1. `apps/web/app/verification/page.tsx` submits a local file and document-version identifier to `POST /api/v1/verification/document`.
2. `apps/api/app/services/verification_service.py::VerificationService.verify_document()` resolves the immutable version and its parent document.
3. `apps/api/app/security/policy.py::PolicyEngine.require_document_read()` authorizes the actor before any registered fingerprint is disclosed.
4. The service hashes only the supplied bytes and compares its digest with `sha256_original`.
5. It returns `VERIFIED` or `HASH_MISMATCH` with expected and actual digests. File content is never persisted or logged.

## FLOW-005 ? Merkle checkpoint

1. An authorized officer calls `POST /api/v1/blockchain/checkpoints` in `apps/api/app/routers/blockchain.py`.
2. `apps/api/app/services/merkle_service.py::MerkleCheckpointService.create_checkpoint()` loads provenance `AuditEvent` rows not already assigned to a `MerkleLeaf`.
3. Each event is canonicalized to stable, sorted JSON and hashed with SHA-256.
4. `build_levels()` constructs a binary Merkle tree, duplicating the last hash only at odd levels.
5. `MerkleBatch` and ordered `MerkleLeaf` records are stored and `get_ledger().record_checkpoint()` commits the private provenance checkpoint.
6. A SHA-256 digest of the batch UUID supplies a globally unique, non-sensitive EVM contract key while `batch_number` remains the human sequence.
7. `apps/api/app/blockchain/public_anchor.py::get_public_anchor_provider()` anchors to local development state, Hardhat, or Polygon Amoy. External failures remain `PENDING_EXTERNAL` rather than fabricating success.
8. `GET /api/v1/blockchain/merkle/{event_id}/proof` reconstructs sibling hashes and verifies the proof locally before returning it.

**Failure paths:** an empty checkpoint returns `409`; unauthorized checkpoint creation returns `403`; an unknown event proof returns `404`.

## FLOW-006 ? Secure case brief and question

1. `apps/web/components/case-workspace.tsx` and `apps/web/app/ai/page.tsx` call `POST /api/v1/ai/case/{case_number}/brief` after the authorized case resolves. The AI page calls `/ask` for subsequent questions.
2. `apps/api/app/ai/case_agent.py::require_case()` checks case assignment and clearance.
3. `apps/api/app/ai/corpus.py::AuthorizedCorpus.for_case()` calls `PolicyEngine.can_view_document()` before returning any chunk.
4. `apps/api/app/ai/retrieval.py::HybridRetriever.retrieve()` scores only the authorized collection.
5. `PromptBuilder` treats evidence as untrusted data; `ClaimValidator` verifies every citation against the supplied chunks.
6. `FactExtractionService` and `ContradictionEngine` compare normalized facts without deciding which source is truthful.
7. `AuditService.record()` records the AI action without logging the question or decrypted evidence.

The frontend renders document titles from validated citation metadata and links each citation to the authorization-filtered document register. Contradictions and missing-information results are visibly separated from supported claims.

**Restricted-intent path:** if Witness-03 is requested but no authorized Witness-03 chunk exists, the response is `INSUFFICIENT_EVIDENCE` with no sources. An active, unexpired grant makes that chunk eligible on the next request.

## FLOW-007 ? Temporary access

1. `apps/web/app/access/page.tsx` sends document ID, subject email, reason and expiry to `POST /api/v1/access/grants`.
2. `apps/api/app/services/access_service.py::AccessService.create_grant()` checks grantor role, case ownership, target status, clearance and a maximum 30-day expiry.
3. The service stores `AccessGrant`, calls `ProvenanceLedger.grant_access()`, records an audit event and creates a notification.
4. `PolicyEngine.can_view_document()` evaluates active status and expiry on every later document, download and AI retrieval request.

`GET /api/v1/access/grants?case_number=...` resolves the case, applies `PolicyEngine.can_view_case()`, and filters returned grants to documents in that case. Revocation records both the case-scoped audit event and ledger provenance event.

## FLOW-007A ? Audit query

1. `apps/web/app/audit/page.tsx` calls `GET /api/v1/audit?case_number={case_number}`.
2. `apps/api/app/routers/audit.py::list_audit_events()` resolves the case number and checks case authorization before querying events.
3. Non-oversight roles remain restricted to actively assigned cases; action and result-limit filters are applied in SQL.
4. Successful development login, case view, AI query, document verification, passport view, access grant/revocation and custody actions create audit rows without evidence plaintext.

## FLOW-008 ? Custody transfer and Evidence Passport

1. `POST /api/v1/evidence/{id}/custody` calls `apps/api/app/services/custody_service.py::CustodyService.transfer()`.
2. The service verifies case access, role and current custodian organization, computes a canonical event hash linked to `previous_event_hash`, then signs the provenance action through the ledger adapter.
3. Audit and notification rows are committed with the operational custody event.
4. `GET /api/v1/evidence/{id}/passport` applies case, classification and associated-document authorization before verifying stored ciphertext, plaintext hash and signature.

## FLOW-009 ? Court verification report

1. The Verification tab calls `GET /api/v1/cases/{case_number}/verification-report`.
2. `apps/api/app/services/report_service.py::VerificationReportService.generate()` filters authorized documents, verifies storage hashes, signatures and version chains, and finds a case-specific Merkle batch.
3. It stores an expiring opaque `VerificationToken` snapshot and returns printable HTML containing Section-63-supporting metadata and a QR code.
4. `GET /api/v1/public/verify/{token}` reveals only hash, signature, version and anchor booleans?never case metadata.

## FLOW-010 ? Request guard

1. `apps/api/app/security/request_guard.py::RequestGuard.middleware()` uses client IP for pre-auth/login budgets so rotating bogus bearer values cannot evade throttling; authenticated route limits remain endpoint-specific.
2. AI/search receives a stricter budget than normal API traffic; excess requests receive `429`.
3. The middleware emits request ID, route, status and latency as structured metadata without request bodies or evidence text.

## FLOW-011 ? Live Fabric submission

1. `apps/api/app/blockchain/ledger.py::FabricProvenanceLedger._invoke()` builds a shell-free peer command containing only commitments, hashes and version/provenance fields.
2. `CORE_PEER_*` selects the read-only mounted PoliceMSP identity; configured peer addresses and TLS roots request PoliceMSP and FSLMSP endorsements.
3. `blockchain/fabric/chaincode/main.go::requireInvokerMSP()` derives the signed MSP and checks the operation allowlist. Claimed organization text is ignored.
4. Both peers endorse, the orderer commits to `justicechannel`, and the CLI waits for valid commit events.
5. The adapter persists the genuine transaction ID. Development failure creates a `DATABASE_DEV` event with `synchronization_pending=true`; production queues `outbox_events` and the separate worker retries with bounded backoff, never fabricating a Fabric ID.

## FLOW-013 ? Durable provider retry

1. Production provenance calls add `OutboxEvent(topic="fabric.{operation}", payload_json=...)` in the same SQL transaction as the case operation.
2. `apps/api/app/services/outbox_service.py::OutboxService.process()` selects due rows with `FOR UPDATE SKIP LOCKED`.
3. It invokes the real `FabricProvenanceLedger`, updates the owning version/custody/grant transaction field, and marks the row `COMPLETED`.
4. Failure increments attempts and schedules exponential retry; ten failed attempts become `FAILED` for operator review.

## FLOW-012 ? Optional encrypted IPFS storage

1. Ingestion encrypts plaintext and wraps its random DEK before selecting storage.
2. `apps/api/app/storage/providers.py::IPFSStorageProvider.store()` posts ciphertext to Kubo `/api/v0/add` with pinning.
3. The protected row stores the CID, two hashes and wrapped DEK; the public chain receives neither CID nor case metadata.
4. Retrieval validates the CID, fetches ciphertext, verifies its hash, then decrypts only after authorization.

## Debugging Entry Points

- Upload failure: `apps/api/app/routers/documents.py`, then `services/document_service.py`, `security/encryption.py`, `storage/providers.py`.
- Authorization failure: `apps/api/app/security/policy.py`, then `security/auth.py`.
- Verification failure: `apps/api/app/routers/verification.py`, then `services/verification_service.py`.
- Merkle failure: `apps/api/app/routers/blockchain.py`, then `services/merkle_service.py` and `blockchain/public_anchor.py`.
- AI citation failure: `apps/api/app/ai/case_agent.py`, then `ai/corpus.py`, `ai/retrieval.py` and `ai/validation.py`.
- Fabric failure: `apps/api/app/blockchain/ledger.py`, then the mounted `peer` identity and `blockchain/fabric/scripts/`.
- Report failure: `apps/api/app/services/report_service.py`, then `services/verification_service.py` and `security/signatures.py`.

## Delivery Validation Flow

1. A push or pull request triggers `.github/workflows/ci.yml`.
2. Independent jobs validate the Python 3.12 API/security suite, Next.js production build, Solidity contract, Fabric chaincode and production Compose interpolation.
3. High-severity dependency audit findings or any test/build failure fail the workflow.
4. `.github/dependabot.yml` proposes weekly dependency updates, which pass through the same validation path.

External IAM, KMS/HSM, government connectors, managed Fabric and Polygon are intentionally outside this untrusted CI environment and have separate tracked integration gates.
