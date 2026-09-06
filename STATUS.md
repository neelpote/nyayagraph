# Current Status

## Working and live-verified

- Docker stack: PostgreSQL/pgvector, Redis, MinIO, FastAPI, Next.js, Kubo IPFS and Hardhat.
- Keycloak-backed OIDC authentication is live locally; case workspace, uploads, versions, AES-256-GCM, SHA-256, service attestations, passports, custody, temporary access, audit, reports, timeline, graph, contradictions and citation-grounded intelligence work.
- Responsive evidence-desk frontend with mobile navigation, consistent icons, accessible focus/reduced-motion behavior, automatic authorized AI briefs, readable citations and review flags.
- The seed now contains 18 explicitly fictional cases, 31 encrypted documents and 35 evidence records. Dataset-wide tests open every case and verify every current document hash and signature.
- The flagship case's 14 document ciphertexts were previously fetched from live MinIO; encrypted hashes and decrypted original hashes matched PostgreSQL.
- A live encrypted 4 KiB payload completed IPFS add → cat → decrypt → unpin.
- Fabric 2.5.16 runs `justicechannel` with local `PoliceMSP` and `FSLMSP`; chaincode is approved and committed on both peers.
- All 31 current document fingerprints have genuine Fabric transaction IDs and all 31 hashes were verified directly through committed chaincode; two flagship custody events are also on Fabric. Offline seed fallbacks can be replayed with `make fabric-sync`.
- Hardhat chain ID 31337 hosts `CaseIntegrityAnchor`; the API committed and verified a Merkle root on Fabric and EVM.
- 73 backend/security tests and five Solidity tests pass. Fabric Go tests/vet, frontend lint/build, Bandit and pip-audit pass; JavaScript dependencies install from locked trees and are monitored through weekly Dependabot updates.
- Versioned KMS envelopes, configurable real LLM/embedding endpoints, rollback object cleanup, a production Fabric outbox worker, fail-closed malware scanning, safe PostgreSQL backup/restore/retention scripts and hardened production Compose configuration are implemented.
- Local Qwen3-8B is integrated through Ollama with structured claims, authorized-source citation validation, a dedicated health endpoint and deterministic fallback when Ollama is not configured.
- GitHub Actions now gates API tests/security scans, frontend lint/build/audit, Solidity tests/audit, Fabric Go tests/vet and production Compose validation; Dependabot tracks all four dependency ecosystems.

## Honest boundaries

- All 18 seeded cases are fictional mock content because government case access is outside this MVP's scope. Runtime screens remain data-driven, not fixed responses.
- Government connector cards remain simulated because no authorized API specifications, credentials or records were supplied; they never claim live connectivity.
- MinIO is the default vault. IPFS is operational but opt-in and receives ciphertext only.
- The local Fabric network has two organizations; production requires managed four-organization infrastructure.
- Polygon Amoy was not used because no funded signer/RPC credentials were supplied; the verified local EVM provider is active.

## Production requirements

- Government IAM/PKI federation details and approved connector credentials. Local Keycloak validates the OIDC implementation but is not a government identity service.
- Reachable NIC/government KMS/HSM gateway and key identifier. The provider boundary exists, but no physical government HSM was supplied for validation.
- Managed four-organization Fabric operations and reconciliation of committed-after-timeout transactions.
- Polygon Amoy RPC, funded testnet-only signer and authority address.
- Encrypted, restore-coherent MinIO/key-volume backups, monitoring/TLS ingress, approved retention and an independent penetration test.
- Any later real-data deployment would require separate legal authorization, data-sharing agreements and approved import mappings; it is not required for this mock-data MVP.

## Launch backlog

The authoritative prioritized backlog is maintained in [GitHub Issues](https://github.com/neelpote/nyayagraph/issues). P0 issues are launch blockers; P1 issues are required production work; P2 issues are measured follow-ups that must not delay the secure core without evidence.
