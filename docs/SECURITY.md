# Security Notes

NyayaGraph separates confidentiality, authorization, authenticity, integrity and provenance rather than presenting an opaque trust score.

- Confidentiality: AES-256-GCM and private storage.
- Authorization: role, case assignment, clearance, relevant active grant and expiry.
- Authenticity: Ed25519 service attestations bound to artifact, submitting actor and hash; replace with government organization/user PKI where required.
- Integrity: original/encrypted SHA-256 and immutable version links.
- Shared provenance: Fabric hash/commitment records or an explicitly labelled development ledger.
- External tamper evidence: Merkle roots on local EVM or Polygon Amoy.
- AI grounding: pre-retrieval ACL, untrusted-evidence prompt boundary and exact citation validation.

Production deployment disables development login and local KEK use. It requires OIDC Government IAM/PKI federation, an external KMS/HSM gateway, TLS/mTLS, managed encrypted database/object storage, Redis-backed distributed rate limits, mandatory malware scanning, the Fabric outbox worker, centralized audit monitoring and secret injection.

## Verification commands

Run `make test` for application/contract regression checks and `make security-test` for dependency and static source audits. Final validation completed 42 backend/security tests, five Solidity tests, zero-finding Python and npm dependency audits, a zero-unresolved-finding Bandit scan, and Fabric Go tests/vet.

Run backend checks with `cd apps/api && ../../.venv/bin/python -m pytest -q`, frontend checks with `npm --prefix apps/web run lint && npm --prefix apps/web run build`, and contract tests with `npm --prefix blockchain/public-anchor test`.
