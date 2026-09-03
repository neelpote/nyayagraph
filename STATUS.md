# Current Status

## Working and live-verified

- Docker stack: PostgreSQL/pgvector, Redis, MinIO, FastAPI, Next.js, Kubo IPFS and Hardhat.
- Keycloak-backed OIDC authentication is live locally; case workspace, uploads, versions, AES-256-GCM, SHA-256, service attestations, passports, custody, temporary access, audit, reports, timeline, graph, contradictions and citation-grounded intelligence work.
- Responsive evidence-desk frontend with mobile navigation, consistent icons, accessible focus/reduced-motion behavior, automatic authorized AI briefs, readable citations and review flags.
- All 14 current document ciphertexts were fetched from MinIO; encrypted hashes and decrypted original hashes match PostgreSQL.
- A live encrypted 4 KiB payload completed IPFS add → cat → decrypt → unpin.
- Fabric 2.5.16 runs `justicechannel` with local `PoliceMSP` and `FSLMSP`; chaincode is approved and committed on both peers.
- All 14 document fingerprints and two custody events have real Fabric transaction IDs; all 14 hashes verify through chaincode.
- Hardhat chain ID 31337 hosts `CaseIntegrityAnchor`; the API committed and verified a Merkle root on Fabric and EVM.
- 42 backend/security tests and five Solidity tests pass. Fabric Go tests/vet, frontend lint/build, Bandit, pip-audit and both npm audits pass without unresolved findings.
- Versioned KMS envelopes, configurable real LLM/embedding endpoints, rollback object cleanup, a production Fabric outbox worker, fail-closed malware scanning, safe PostgreSQL backup/restore/retention scripts and hardened production Compose configuration are implemented.

## Honest boundaries

- `MH-PUNE-2026-00142` is optional synthetic demo content because no authorized government credentials or case records were supplied. Runtime screens are data-driven, not fixed responses.
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
- Authorized real case imports replacing the optional demo seed.
