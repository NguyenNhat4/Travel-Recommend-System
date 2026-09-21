PYTHON ?= python
AS_OF ?= $(shell date +%F)
SEED ?= 42
CATALOG_SNAPSHOT ?= data_collection/snapshots/2026-09-21/products.jsonl.gz
LOCAL_SEED_DATABASE_URL = postgresql://postgres:postgres@localhost:5432/vota
LOCAL_INSIDER_DATABASE_URL = postgresql://postgres:postgres@localhost:5432/insider

.PHONY: demo-db demo-db-reset verify-db backend

demo-db:
	docker compose up -d --wait postgres
	cd src && SEED_DATABASE_URL=$(LOCAL_SEED_DATABASE_URL) INSIDER_DATABASE_URL=$(LOCAL_INSIDER_DATABASE_URL) $(PYTHON) -m data_collection.seed --products $(CATALOG_SNAPSHOT) --as-of $(AS_OF) --seed $(SEED)
	$(MAKE) verify-db

demo-db-reset:
	docker compose up -d --wait postgres
	cd src && SEED_DATABASE_URL=$(LOCAL_SEED_DATABASE_URL) INSIDER_DATABASE_URL=$(LOCAL_INSIDER_DATABASE_URL) $(PYTHON) -m data_collection.seed --products $(CATALOG_SNAPSHOT) --as-of $(AS_OF) --seed $(SEED) --reset
	$(MAKE) verify-db

verify-db:
	docker compose exec -T postgres psql -U postgres -d vota < db/verify.sql
	docker compose exec -T postgres psql -U postgres -d insider < db/verify_insider.sql

backend:
	$(PYTHON) -m uvicorn src.backend.app.main:app --reload
