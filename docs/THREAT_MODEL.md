# Threat Model

## Protected assets

Evidence plaintext, document keys, person identities, case assignments, custody records, signatures, audit history and AI retrieval context.

## Trust boundaries

- browser to FastAPI over authenticated API calls;
- FastAPI to PostgreSQL, MinIO and Redis;
- application identity to Fabric peer/MSP;
- checkpoint signer to local/Polygon EVM;
- authorized chunks to any configured LLM.

## Main threats and controls

| Threat | Control |
|---|---|
| IDOR/cross-case access | DB-resolved user, case assignment, clearance and resource grant checks before hash/retrieval/download |
| Object-store disclosure | AES-256-GCM ciphertext only; wrapped DEK; plaintext DEKs never stored |
| Tampering | Original/encrypted SHA-256, authenticated encryption, Ed25519 signature, version hash chain, custody hash chain, Merkle proof |
| Prompt injection | Evidence treated as untrusted, no document tools/instructions, authorization before retrieval, claim/citation validation |
| Cross-case AI leakage | Authorized corpus is constructed before scoring; output sources must belong to supplied chunks |
| Public-chain privacy leak | Only root, batch and commitment; no case identifiers or storage references |
| Malicious upload | bounded reads, suffix/MIME agreement, page/pixel limits, structural parsing, archive rejection and mandatory production ClamAV scanning |
| Secret exposure | `.env` ignored, weak production keys rejected, development KEK mode 0600, Docker data volume excluded from build context |
| Audit probing | scoped audit queries and opaque public verification tokens |
| Abuse | IP-safe pre-auth and endpoint process-local limits for MVP; Redis required before multi-replica deployment |

## Residual MVP risk

Local Keycloak is not government IAM; local KEK is not an HSM; browser password grant/session storage must become authorization-code + PKCE/BFF cookies; the limiter is process-local; Fabric retry needs committed-after-timeout reconciliation; MinIO/key backups and independent penetration testing remain deployment gates. Government integrations are simulations until authorized access is supplied.
