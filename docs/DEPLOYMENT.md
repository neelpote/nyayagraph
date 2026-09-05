# Deployment

The default Compose stack is for development and hackathon demonstration. Its
credentials are intentionally labelled `dev-only`, service ports bind to
localhost, and PostgreSQL/Redis are not published to the host.

1. Copy `.env.example` to `.env` if you want to change the development defaults.
2. Run `make up`, `make migrate`, `make seed`.
3. Keep `FABRIC_ENABLED=false`, `ENABLE_NEO4J=false` and `PUBLIC_CHAIN_MODE=local` until optional providers are configured.
4. Enable Neo4j/Keycloak through their Compose profiles when required.
5. Configure Fabric peer/MSP environment before setting `FABRIC_ENABLED=true`.
6. Deploy `CaseIntegrityAnchor`, set its address/RPC/chain ID, then use `PUBLIC_CHAIN_MODE=hardhat` or `polygon_amoy`.

## Production guardrails

Use both Compose files; the production override removes every published port,
uses Keycloak's production command, disables development mode and refuses to
render until OIDC, external KMS, AI provider, malware scanner, database and signing-key configuration is supplied:

```sh
docker compose -f docker-compose.yml -f infra/compose.production.yml config --quiet
docker compose -f docker-compose.yml -f infra/compose.production.yml up -d
```

Provide secrets through the deployment platform rather than committing a
production `.env`. Attach an approved TLS gateway to the Compose network or add
a site-specific override that publishes only the gateway. Compose images are
pinned by registry digest (tags remain for readability); update and
vulnerability-scan those pins deliberately.

The locally built API image still runs as root and both local Dockerfiles use
unpinned base images because those files are outside this operations patch.
Rebuild the API with a dedicated UID and pin both build inputs before treating
this Compose stack as a production baseline. Also configure
Government IAM federation, reachable KMS/HSM, Fabric mTLS, monitored audit
export, the outbox worker, and object-storage versioning/object lock. Do
not use seeded users or data.

## PostgreSQL backups

Backups are private (`umask 077`), use PostgreSQL's custom format, and are
atomically renamed only after a successful dump. Store them outside the source
tree on encrypted, access-controlled storage:

```sh
BACKUP_DIR=/var/backups/nyayagraph make backup
CONFIRM_RESTORE=nyayagraph make restore BACKUP=/var/backups/nyayagraph/nyayagraph-postgres-YYYYMMDDTHHMMSSZ.dump
BACKUP_DIR=/var/backups/nyayagraph RETENTION_DAYS=30 make retention
BACKUP_DIR=/var/backups/nyayagraph RETENTION_DAYS=30 CONFIRM_RETENTION=delete make retention
```

Retention is a dry run unless explicitly confirmed. Restore validates the dump
catalog first, but is destructive and should be exercised regularly in an
isolated environment. These scripts cover PostgreSQL only; back up MinIO and
the API data volume with storage-native snapshots, versioning, and object lock.
