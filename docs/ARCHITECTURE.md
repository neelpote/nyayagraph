# Architecture

NyayaGraph is a modular monolith optimized for a 36-hour MVP. Next.js calls one FastAPI boundary; routers remain thin, services own workflows, policy/domain code makes deterministic decisions, repositories/providers isolate databases and infrastructure.

```text
Next.js case workspace
        |
FastAPI authentication + request guard
        |
Router -> Service -> Policy/domain -> Repository/provider
        |                  |              |
 PostgreSQL/pgvector   AES/signatures   MinIO
        |                                 |
 PostgreSQL graph fallback          encrypted evidence
        |
 Fabric adapter -> Merkle batch -> Hardhat / Polygon Amoy
```

PostgreSQL is authoritative for operational state. Redis is cache/rate-limit infrastructure but holds no authoritative evidence. MinIO receives only AES-256-GCM ciphertext. Neo4j, Keycloak, IPFS, Fabric and an external LLM are optional provider boundaries; their absence does not collapse the core case workspace.

Fabric uses one shared `justicechannel` for PoliceMSP, FSLMSP, ProsecutionMSP and CourtMSP. Chaincode stores hashes, commitments, version numbers and organization provenance?not evidence, identities or case narratives.

The public EVM contract stores a Merkle root, opaque batch number and metadata commitment. No case ID, FIR, identity, CID, storage reference or evidence type is public.

See `FLOW.md` for the implemented call paths and `DECISIONS.md` for rationale.
