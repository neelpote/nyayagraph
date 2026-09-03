# NyayaGraph Setup

## macOS

Docker Desktop is recommended, especially on Apple Silicon.

```bash
brew install git node python jq openssl
```

NyayaGraph requires Python 3.12 or newer. The API container uses Python 3.12.

Install and start Docker Desktop, then verify:

```bash
node -v
npm -v
python3 --version
docker --version
docker compose version
git --version
```

## Windows

Install Git, Node.js LTS, Python 3.12 and Docker Desktop. Enable WSL2:

```powershell
wsl --install
wsl --set-default-version 2
```

Restart if requested, open Ubuntu in WSL2, enable Docker Desktop’s WSL integration, and run the repository commands from the WSL terminal.

## Ubuntu/Linux

```bash
sudo apt update
sudo apt install -y git nodejs npm python3 python3-venv python3-pip jq openssl docker.io docker-compose-plugin
sudo usermod -aG docker "$USER"
```

Sign out and back in after changing the Docker group.
For local non-Docker execution, confirm that `python3 --version` is 3.12 or newer; otherwise use the Docker workflow or install Python 3.12 from your distribution's supported repository.

## Configure and start

```bash
git clone <repository>
cd nyayagraph
cp .env.example .env
```

For repeatable development secrets:

```bash
openssl rand -base64 32
openssl rand -hex 32
```

Place the first value in `MASTER_KEK_BASE64` and the second in `JWT_SECRET`. Do not commit `.env`.
Replace every `change_me` database, MinIO, Neo4j, and optional Keycloak value before starting the stack, and keep the password embedded in `DATABASE_URL` consistent with `POSTGRES_PASSWORD`.

```bash
make up
make migrate
make seed
make demo
```

The API container applies Alembic automatically on startup; `make migrate` is safe and makes the step explicit.

## Local fallback without Docker

Use this only for development:

```bash
make install
cd apps/api
DATABASE_URL=sqlite:///./data/nyayagraph.db STORAGE_BACKEND=local ../../.venv/bin/alembic upgrade head
DATABASE_URL=sqlite:///./data/nyayagraph.db STORAGE_BACKEND=local ../../.venv/bin/python -m app.seed --reset
DATABASE_URL=sqlite:///./data/nyayagraph.db STORAGE_BACKEND=local ../../.venv/bin/uvicorn app.main:app --reload
```

In another terminal:

```bash
npm --prefix apps/web run dev
```

## Optional services

```bash
docker compose --profile graph up -d neo4j
docker compose --profile keycloak up -d keycloak
```

Fabric requires the official Fabric 2.5 samples and binaries:

```bash
export FABRIC_SAMPLES_DIR=/absolute/path/to/fabric-samples
make fabric-up
```

The local bootstrap maps the two official sample organizations to `PoliceMSP` and `FSLMSP`, deploys the chaincode, and recreates the API with Fabric enabled. The target deployment adds ProsecutionMSP and CourtMSP.

Encrypted IPFS is optional:

```bash
make ipfs-up
```

Set `IPFS_ENABLED=true` and `STORAGE_BACKEND=ipfs` only when new encrypted uploads should use IPFS. Existing MinIO references continue to resolve through their original provider.

Hardhat local chain:

```bash
npm --prefix blockchain/public-anchor run node
```

Then deploy with `make blockchain-deploy`. Copy the printed contract address into `.env` as `PUBLIC_ANCHOR_CONTRACT`, set `PUBLIC_CHAIN_MODE=hardhat`, and recreate the API.

## Reset

`make demo-reset` deletes and recreates only NyayaGraph synthetic rows. It does not delete Docker volumes. Use `make down` to stop services.
