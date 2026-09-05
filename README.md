# NyayaGraph

**From Case Files to Verifiable Case Intelligence.**

NyayaGraph is a privacy-preserving case-intelligence and evidence-provenance MVP for SIH26190. It sits above CCTNS, ICJS, eSakshya, eCourts, eForensics, eProsecution and ePrisons; the included adapters are simulations and do not claim live government connectivity.

The primary experience is: **enter `MH-PUNE-2026-00142` ? see the complete authorized, attributable and verifiable case**.

## What works

- live Keycloak/OIDC login and deterministic organization/case/clearance/grant policy;
- 18 explicitly fictional mock cases across more than ten case types and five workflow states;
- one full flagship case with 14 documents and 18 evidence records, plus one encrypted, signed and provenance-registered document/evidence pair for each additional case;
- AES-256-GCM encrypted object storage, versioned KMS envelopes, SHA-256 fingerprints and Ed25519 service attestations;
- exact duplicate detection, immutable versions and authenticated download;
- Evidence Passport, custody hash chain, audit log and time-bound access;
- authorization-first AI brief, exact citations, search and contradiction detection, with configurable real LLM/embedding providers;
- PostgreSQL/pgvector graph and retrieval fallback, optional Neo4j boundary;
- Hyperledger Fabric chaincode/adapter with honest database-ledger fallback;
- Merkle batches/proofs and local Hardhat or optional Polygon Amoy anchoring;
- printable court verification HTML with privacy-safe QR verification.

AI is read-only investigative support. It does not infer guilt, make legal conclusions, change evidence, transfer custody or grant access.

## Quick start

```bash
git clone https://github.com/neelpote/nyayagraph.git
cd nyayagraph
cp .env.example .env

make up
make migrate
make seed
make demo
make test
make security-test
```

When Fabric is enabled later, `make fabric-up` also synchronizes document fingerprints that were safely stored in database-ledger fallback mode while peers were offline.

Open:

- Frontend: [http://localhost:3000](http://localhost:3000)
- Backend: [http://localhost:8000](http://localhost:8000)
- Swagger: [http://localhost:8000/docs](http://localhost:8000/docs)
- MinIO: [http://localhost:9001](http://localhost:9001)
- Neo4j when enabled: [http://localhost:7474](http://localhost:7474)
- Keycloak when enabled: [http://localhost:8080](http://localhost:8080)

## Demo users

All development accounts use `NyayaDemo!2026`:

| Account | Role |
|---|---|
| `io@nyaya.local` | Investigating Officer |
| `fsl@nyaya.local` | FSL Officer |
| `expert@nyaya.local` | External Expert |
| `auditor@nyaya.local` | Auditor |

These credentials exist only in the imported local Keycloak realm and fictional mock seed. They are never production credentials. Every mock case and generated artifact identifies itself as fictional and contains no real person or government record.

## Core demo

1. Sign in as the investigating officer and open `MH-PUNE-2026-00142`.
2. Review the cited AI brief, timeline and knowledge graph.
3. Open E-12 to see hashes, signature, custody warning and ledger status.
4. Verify `seed/documents/forensic-original.pdf`; expect `VERIFIED`.
5. Verify `seed/documents/forensic-modified.pdf`; expect `HASH_MISMATCH`.
6. Sign in as the external expert and ask about Witness-03; expect insufficient authorized evidence.
7. As the IO, grant `expert@nyaya.local` temporary access to Witness-03.
8. Ask again; the restricted statement appears with its citation and an audit/provenance event.
9. Generate the court verification report from the case Verification tab.

## Blockchain modes

NyayaGraph uses two ledger layers:

- **Hyperledger Fabric** (`PoliceMSP`, `FSLMSP`, `ProsecutionMSP`, `CourtMSP`) stores hashes and provenance on one shared `justicechannel`. It never stores evidence files or case text.
- **EVM checkpoint** uses local Hardhat for development or Polygon Amoy optionally. It receives only a Merkle root, batch number and metadata commitment.

The default keeps `FABRIC_ENABLED=false` and `PUBLIC_CHAIN_MODE=local` so the app starts without external networks. These modes are visibly labelled and never impersonate real transactions.

Fabric setup:

```bash
export FABRIC_SAMPLES_DIR=/absolute/path/to/fabric-samples
make fabric-up
```

The local bootstrap renames the sample identities to `PoliceMSP` and `FSLMSP`; chaincode authorization is based on signed MSP identity, never a caller-supplied organization string.

Local EVM setup (two terminals):

```bash
npm --prefix blockchain/public-anchor run node
npm --prefix blockchain/public-anchor run deploy:local
```

Copy the printed address to `PUBLIC_ANCHOR_CONTRACT`, set `PUBLIC_CHAIN_MODE=hardhat`, and restart the API. Start the optional encrypted IPFS tier with `make ipfs-up`; it is never used for plaintext.

## Commands

```bash
make install
make up
make down
make logs
make migrate
make seed
make test
make fabric-up
make fabric-down
make blockchain-deploy
make demo-reset
make demo
make outbox
```

## Security notes

- Generate development secrets with `openssl rand -base64 32` for `MASTER_KEK_BASE64` and `openssl rand -hex 32` for `JWT_SECRET`.
- Never commit `.env`, KMS material, Fabric MSP credentials or blockchain private keys.
- Production requires the HTTPS NIC/government KMS/HSM gateway configuration; local KEK use fails closed outside development.
- The QR endpoint reveals authenticity booleans only, never confidential case data.
- ?Section-63-supporting metadata? supports human/legal verification and is not a claim of automatic admissibility.

## Troubleshooting

- **Ports already used:** change host ports in `docker-compose.yml` or stop the conflicting service.
- **Docker unavailable:** start Docker Desktop and confirm `docker compose version`.
- **PostgreSQL/pgvector failure:** verify the `pgvector/pgvector:pg16` container, then run `make migrate`.
- **MinIO unavailable:** verify its endpoint and credentials. Production never silently falls back to local storage.
- **Neo4j unavailable:** keep `ENABLE_NEO4J=false`; PostgreSQL graph data remains functional.
- **Keycloak unavailable:** use `AUTH_MODE=dev_jwt` for the MVP. Dev login is disabled outside development.
- **Fabric peer unavailable:** the API reports pending synchronization with a `dev-ledger-*` ID; inspect the MSP and peer environment.
- **Chaincode not committed:** rerun `blockchain/fabric/scripts/fabric-deploy-chaincode.sh`.
- **Contract address missing:** deploy Hardhat and set `PUBLIC_ANCHOR_CONTRACT`; checkpoints otherwise remain local/pending.
- **LLM unavailable:** case metadata, hashes, timeline, custody, deterministic brief and integrity checks still work.

## Known MVP limitations

Government integrations remain simulated until authorized specifications, credentials and records are provided. Local Keycloak validates OIDC but is not Government IAM; the KMS/HSM adapter cannot validate a physical NIC key without access. OCR is not enabled for scanned images, the limiter is process-local, and SQLite is only for tests. See `STATUS.md`.

## Engineering documentation

- [Project Context](CONTEXT.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Execution Flow](FLOW.md)
- [Engineering Decisions](DECISIONS.md)
- [Threat Model](docs/THREAT_MODEL.md)
- [Demo Guide](docs/DEMO.md)
- [API Guide](docs/API.md)
- [Security](docs/SECURITY.md)
- [Deployment](docs/DEPLOYMENT.md)
- [Setup](SETUP.md)
