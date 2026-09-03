.DEFAULT_GOAL := up
PYTHON ?= python3
.PHONY: install up down logs migrate seed test security-test fabric-up fabric-down blockchain-deploy ipfs-up demo-reset demo backup restore retention outbox production-check

install:
	$(PYTHON) -c 'import sys; assert sys.version_info >= (3, 12), "NyayaGraph requires Python 3.12+"'
	$(PYTHON) -m venv .venv
	.venv/bin/pip install -r apps/api/requirements-dev.txt
	npm --prefix apps/web ci
	npm --prefix blockchain/public-anchor ci

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f

migrate:
	docker compose exec api alembic upgrade head

seed:
	docker compose exec api python -m app.seed

test:
	docker compose exec -e FABRIC_ENABLED=false -e IPFS_ENABLED=false -e ENABLE_NEO4J=false -e PUBLIC_CHAIN_MODE=mock api python -m pytest -q
	npm --prefix apps/web run lint
	npm --prefix blockchain/public-anchor test
	cd blockchain/fabric/chaincode && go test ./... && go vet ./...

security-test:
	docker compose exec api python -m pip install --disable-pip-version-check -q -r requirements-dev.txt
	docker compose exec api python -m pip_audit -r requirements.txt
	docker compose exec api bandit -q -r app

fabric-up:
	./blockchain/fabric/scripts/fabric-up.sh
	./blockchain/fabric/scripts/fabric-deploy-chaincode.sh
	FABRIC_ENABLED=true docker compose up -d --force-recreate api web

fabric-down:
	./blockchain/fabric/scripts/fabric-down.sh

blockchain-deploy:
	docker compose --profile chain up -d hardhat
	docker compose exec hardhat npm run deploy:local

ipfs-up:
	docker compose --profile ipfs up -d ipfs

demo-reset:
	docker compose exec api python -m app.seed --reset

demo:
	./scripts/verify-demo.sh

backup:
	./scripts/backup.sh

restore:
	./scripts/restore.sh $(BACKUP)

retention:
	./scripts/retention.sh

outbox:
	docker compose exec api python -m app.services.outbox_service

production-check:
	docker compose -f docker-compose.yml -f infra/compose.production.yml config --quiet
