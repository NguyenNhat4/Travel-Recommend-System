SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.ONESHELL:

PYTHON ?= python
AS_OF ?= $(shell date +%F)
SEED ?= 42
CATALOG_SNAPSHOT ?= data_collection/snapshots/2026-09-30/products.jsonl.gz
# Cổng host của Postgres; đổi khi máy đã có Postgres khác giữ 5432.
# Phải khớp POSTGRES_HOST_PORT dùng cho `docker compose up`.
POSTGRES_HOST_PORT ?= 5432
export POSTGRES_HOST_PORT
LOCAL_SEED_DATABASE_URL = postgresql://postgres:postgres@localhost:$(POSTGRES_HOST_PORT)/vota
# .ONESHELL: mọi dòng của một recipe chạy chung shell, nên `cd` phải nằm trong subshell `( … )`.
# Runner migration cần psycopg; venv của backend có sẵn, nếu chưa tạo thì rơi về $(PYTHON).
MIGRATE_PYTHON = $(shell test -x src/backend/.venv/bin/python && echo src/backend/.venv/bin/python || echo $(PYTHON))
LOCAL_INSIDER_DATABASE_URL = postgresql://postgres:postgres@localhost:$(POSTGRES_HOST_PORT)/insider

.PHONY: tunnel tunnel-down tunnel-status chat web demo-db demo-db-reset verify-db index-vectors db-migrate db-migrate-status update backend backend-logs backend-stop backend-local jwt-keys

# SSH tunnel tới DB staging: primary (ghi) :15432, replica (đọc) :15433. Mật khẩu đọc từ .env.tunnel (gitignore),
# nạp qua SSH_ASKPASS nên không cần sshpass. Chạy nền; dừng bằng `make tunnel-down`.
TUNNEL_PRIMARY = 127.0.0.1:15432:10.148.0.2:5432 vota-dev@35.197.148.180
TUNNEL_REPLICA = 127.0.0.1:15433:10.148.0.4:5432 vota-dev@34.126.70.1
tunnel:
	if [[ ! -f .env.tunnel ]]; then echo "Thiếu .env.tunnel (SSH_PRIMARY_PASSWORD, SSH_REPLICA_PASSWORD)"; exit 1; fi
	ASKPASS="$$(mktemp)"; trap 'rm -f "$$ASKPASS"' EXIT
	printf '#!/bin/sh\nprintf %%s "$$TUNNEL_PW"\n' > "$$ASKPASS"; chmod 700 "$$ASKPASS"
	open_tunnel() { # $$1=tên $$2=cổng local $$3=biến mật khẩu $$4=spec "-L ... user@host"
		if (exec 3<>/dev/tcp/127.0.0.1/$$2) 2>/dev/null; then echo "$$1: cổng $$2 đã mở, bỏ qua"; return; fi
		PW="$$(sed -n "s/^$$3=//p" .env.tunnel | tail -n 1)"
		if [[ -z "$$PW" ]]; then echo "$$1: thiếu $$3 trong .env.tunnel"; exit 1; fi
		TUNNEL_PW="$$PW" SSH_ASKPASS="$$ASKPASS" SSH_ASKPASS_REQUIRE=force setsid ssh -f -N \
			-o PreferredAuthentications=password -o PubkeyAuthentication=no \
			-o ExitOnForwardFailure=yes -o StrictHostKeyChecking=accept-new \
			-o ServerAliveInterval=30 -L $$4
		echo "$$1: tunnel mở trên :$$2"
	}
	open_tunnel primary 15432 SSH_PRIMARY_PASSWORD "$(TUNNEL_PRIMARY)"
	open_tunnel replica 15433 SSH_REPLICA_PASSWORD "$(TUNNEL_REPLICA)"

tunnel-down:
	pkill -f "ssh -f -N .*-L 127.0.0.1:1543[23]:" && echo "Đã tắt tunnel" || echo "Không có tunnel đang chạy"

tunnel-status:
	for p in 15432 15433; do
		if (exec 3<>/dev/tcp/127.0.0.1/$$p) 2>/dev/null; then echo ":$$p mở"; else echo ":$$p đóng"; fi
	done
.PHONY: recsys-test recsys-gate-run recsys-regress recsys-baseline

# Chạy trọn bộ FastAPI + Streamlit; Ctrl+C sẽ dừng cả hai.
# Agent mặc định gọi engine trong tiến trình (inprocess); ITINERARY_DATA_MODE=http để gọi qua ITINERARY_SERVICE_BASE_URL.
chat:
	@PROJECT_DIR="$$(pwd)"
	PYTHON_BIN="$${PROJECT_DIR}/.venv/bin/python"
	BACKEND_PORT="$${BACKEND_PORT:-8000}"
	STREAMLIT_PORT="$${STREAMLIT_PORT:-8502}"
	LOG_FILE="$${AGENT_DEMO_LOG_FILE:-$${PROJECT_DIR}/.logs/agent-demo.log}"
	if [[ ! -x "$${PYTHON_BIN}" ]]; then
		echo "Không tìm thấy .venv. Hãy chạy:"
		echo "  python3 -m venv .venv"
		echo "  .venv/bin/pip install -r src/backend/requirements.txt -r src/evaluation/requirements.txt"
		exit 1
	fi
	cleanup() {
		if [[ -n "$${BACKEND_PID:-}" ]]; then
			kill "$${BACKEND_PID}" 2>/dev/null || true
			wait "$${BACKEND_PID}" 2>/dev/null || true
		fi
	}
	trap cleanup EXIT INT TERM
	export ITINERARY_DATA_MODE="$${ITINERARY_DATA_MODE:-inprocess}"
	export ITINERARY_SERVICE_BASE_URL="$${ITINERARY_SERVICE_BASE_URL:-http://127.0.0.1:$${BACKEND_PORT}}"
	export ITINERARY_LLM_TIMEOUT_SECONDS="$${ITINERARY_LLM_TIMEOUT_SECONDS:-30}"
	export ITINERARY_REQUEST_TIMEOUT_SECONDS="$${ITINERARY_REQUEST_TIMEOUT_SECONDS:-90}"
	export ASSISTANT_API_BASE_URL="$${ASSISTANT_API_BASE_URL:-http://127.0.0.1:$${BACKEND_PORT}/api/v1}"
	mkdir -p "$$(dirname "$${LOG_FILE}")"
	touch "$${LOG_FILE}"
	echo "Log được lưu tại $${LOG_FILE}"
	echo "Khởi động FastAPI tại http://127.0.0.1:$${BACKEND_PORT}"
	"$${PYTHON_BIN}" -m uvicorn src.backend.app.main:app \
		--host 127.0.0.1 --port "$${BACKEND_PORT}" \
		> >(tee -a "$${LOG_FILE}") 2>&1 &
	BACKEND_PID=$$!
	echo "Đang chờ FastAPI tải model và khởi động..."
	BACKEND_READY=false
	for _ in $$(seq 1 300); do
		if ! kill -0 "$${BACKEND_PID}" 2>/dev/null; then
			echo "FastAPI đã dừng khi khởi động."
			exit 1
		fi
		if curl --silent --fail --max-time 1 \
			"http://127.0.0.1:$${BACKEND_PORT}/api/v1/assistant/status" >/dev/null; then
			BACKEND_READY=true
			break
		fi
		sleep 1
	done
	if [[ "$${BACKEND_READY}" != "true" ]]; then
		echo "FastAPI chưa sẵn sàng sau 300 giây. Xem log tại $${LOG_FILE}."
		exit 1
	fi
	echo "Mở UI tại http://127.0.0.1:$${STREAMLIT_PORT}"
	echo "Nhấn Ctrl+C để dừng cả hai process."
	"$${PYTHON_BIN}" -m streamlit run src/evaluation/agent/streamlit_app.py \
		--server.port "$${STREAMLIT_PORT}" \
		> >(tee -a "$${LOG_FILE}") 2>&1

# Chạy web chính (Next :3000 + BFF :3001) cùng FastAPI :8000; Ctrl+C dừng cả hai.
# Lưu ý: chat trong web hiện gọi /api/assistant/chat của BFF (Gemini), CHƯA gọi
# /api/v1/assistant/itineraries của FastAPI. FastAPI ở đây phục vụ các API khác
# và để sẵn cho lúc Web nối vào agent. Data mode của agent như target chat (mặc định inprocess).
web:
	@PROJECT_DIR="$$(pwd)"
	PYTHON_BIN="$${PROJECT_DIR}/.venv/bin/python"
	FRONTEND_DIR="$${PROJECT_DIR}/src/frontend"
	BACKEND_PORT="$${BACKEND_PORT:-8000}"
	ROOT_BACKEND_BASE_URL=""
	if [[ -f "$${PROJECT_DIR}/.env" ]]; then
		ROOT_BACKEND_BASE_URL="$$(sed -n 's/^BACKEND_BASE_URL=//p' "$${PROJECT_DIR}/.env" | tail -n 1)"
	fi
	export BACKEND_BASE_URL="$${BACKEND_BASE_URL:-$${ROOT_BACKEND_BASE_URL:-http://127.0.0.1:$${BACKEND_PORT}}}"
	LOG_FILE="$${WEB_DEMO_LOG_FILE:-$${PROJECT_DIR}/.logs/web-demo.log}"
	if [[ ! -x "$${PYTHON_BIN}" ]]; then
		echo "Không tìm thấy .venv. Hãy chạy:"
		echo "  python3 -m venv .venv"
		echo "  .venv/bin/pip install -r src/backend/requirements.txt"
		exit 1
	fi
	if ! command -v npm >/dev/null 2>&1; then
		echo "Không tìm thấy npm. Cần Node.js để chạy web chính."
		exit 1
	fi
	if [[ ! -d "$${FRONTEND_DIR}/node_modules" ]]; then
		echo "Chưa cài dependency của frontend, đang chạy npm install..."
		npm --prefix "$${FRONTEND_DIR}" install
	fi
	cleanup() {
		if [[ -n "$${BACKEND_PID:-}" ]]; then
			kill "$${BACKEND_PID}" 2>/dev/null || true
			wait "$${BACKEND_PID}" 2>/dev/null || true
		fi
	}
	trap cleanup EXIT INT TERM
	export ITINERARY_DATA_MODE="$${ITINERARY_DATA_MODE:-inprocess}"
	export ITINERARY_SERVICE_BASE_URL="$${ITINERARY_SERVICE_BASE_URL:-http://127.0.0.1:$${BACKEND_PORT}}"
	export ITINERARY_LLM_TIMEOUT_SECONDS="$${ITINERARY_LLM_TIMEOUT_SECONDS:-30}"
	export ITINERARY_REQUEST_TIMEOUT_SECONDS="$${ITINERARY_REQUEST_TIMEOUT_SECONDS:-90}"
	mkdir -p "$$(dirname "$${LOG_FILE}")"
	touch "$${LOG_FILE}"
	echo "Log được lưu tại $${LOG_FILE}"
	echo "Khởi động FastAPI tại http://127.0.0.1:$${BACKEND_PORT}"
	"$${PYTHON_BIN}" -m uvicorn src.backend.app.main:app \
		--host 127.0.0.1 --port "$${BACKEND_PORT}" \
		> >(tee -a "$${LOG_FILE}") 2>&1 &
	BACKEND_PID=$$!
	echo "Đang chờ FastAPI tải model và khởi động..."
	BACKEND_READY=false
	for _ in $$(seq 1 300); do
		if ! kill -0 "$${BACKEND_PID}" 2>/dev/null; then
			echo "FastAPI đã dừng khi khởi động."
			exit 1
		fi
		if curl --silent --fail --max-time 1 \
			"http://127.0.0.1:$${BACKEND_PORT}/api/v1/assistant/status" >/dev/null; then
			BACKEND_READY=true
			break
		fi
		sleep 1
	done
	if [[ "$${BACKEND_READY}" != "true" ]]; then
		echo "FastAPI chưa sẵn sàng sau 300 giây. Xem log tại $${LOG_FILE}."
		exit 1
	fi
	echo "Mở web tại http://localhost:3000 (Next BFF cùng cổng :3000)"
	echo "Nhấn Ctrl+C để dừng cả hai process."
	npm --prefix "$${FRONTEND_DIR}" run dev \
		> >(tee -a "$${LOG_FILE}") 2>&1

demo-db:
	docker compose up -d --wait postgres
	$(MAKE) db-migrate
	(cd src && SEED_DATABASE_URL=$(LOCAL_SEED_DATABASE_URL) INSIDER_DATABASE_URL=$(LOCAL_INSIDER_DATABASE_URL) "$(PYTHON)" -m data_collection.seed --products $(CATALOG_SNAPSHOT) --as-of $(AS_OF) --seed $(SEED))
	$(MAKE) verify-db

demo-db-reset:
	docker compose up -d --wait postgres
	$(MAKE) db-migrate
	(cd src && SEED_DATABASE_URL=$(LOCAL_SEED_DATABASE_URL) INSIDER_DATABASE_URL=$(LOCAL_INSIDER_DATABASE_URL) "$(PYTHON)" -m data_collection.seed --products $(CATALOG_SNAPSHOT) --as-of $(AS_OF) --seed $(SEED) --reset)
	$(MAKE) verify-db

verify-db:
	docker compose exec -T postgres psql -U postgres -d vota < db/verify.sql
	docker compose exec -T postgres psql -U postgres -d insider < db/verify_insider.sql

# Cài thêm dependency khi requirements.txt hoặc package.json đổi (vd sau git pull). Không đụng DB hay dữ liệu.
# Venv: .venv (make web/chat dùng) hoặc src/backend/.venv (README dùng), cái nào có trước.
update:
	@VENV="$$(for v in .venv src/backend/.venv; do [[ -x $$v/bin/python ]] && echo $$v && break; done || true)"
	if [[ -z "$${VENV}" ]]; then
		echo "Không tìm thấy venv. Hãy chạy: python3 -m venv .venv"
		exit 1
	fi
	echo "==> Python: $${VENV}"
	"$${VENV}/bin/python" -m pip install -r src/backend/requirements.txt -r src/evaluation/requirements.txt
	if ! command -v npm >/dev/null 2>&1; then
		echo "Không tìm thấy npm. Cần Node.js để cập nhật frontend."
		exit 1
	fi
	echo "==> Frontend: src/frontend"
	npm --prefix src/frontend install
	echo "Đã cập nhật dependency."

# Embed toàn catalog bằng e5-small trên CPU (vài phút) nên không tự chạy trong demo-db.
index-vectors:
	docker compose up -d --wait postgres weaviate
	$(PYTHON) -m src.backend.jobs.embed_products

# Áp thay đổi schema lên database ĐANG CÓ DỮ LIỆU, không xoá gì (db/migrations/README.md).
# db/init/*.sql chỉ chạy lúc initdb trên volume rỗng nên không dùng được cho máy đã seed.
db-migrate:
	docker compose up -d --wait postgres
	SEED_DATABASE_URL=$(LOCAL_SEED_DATABASE_URL) "$(MIGRATE_PYTHON)" db/migrations/run.py

db-migrate-status:
	SEED_DATABASE_URL=$(LOCAL_SEED_DATABASE_URL) "$(MIGRATE_PYTHON)" db/migrations/run.py --status

backend:
	docker compose up -d --build backend
	@echo "Backend API: http://localhost:$${BACKEND_PORT:-8000}"

backend-logs:
	docker compose logs -f backend

# Chỉ dừng Backend; PostgreSQL và volume dữ liệu được giữ nguyên.
backend-stop:
	docker compose stop backend

# Chạy trực tiếp trên máy khi cần reload nhanh, không dùng container Backend.
backend-local:
	ITINERARY_DATA_MODE=$${ITINERARY_DATA_MODE:-fixture} \
		$(PYTHON) -m uvicorn src.backend.app.main:app --reload --host 127.0.0.1 --port $${BACKEND_PORT:-8000}

# Cặp khoá RS256 cho JWT (docs/spec/hop-dong-tich-hop-auth.md §10.2, §19). secrets/ nằm trong .gitignore;
# không commit, không đưa vào image. Đã có thì giữ nguyên để không làm mất hiệu lực token đang dùng.
jwt-keys:
	mkdir -p secrets
	if [ -f secrets/jwt-private.pem ]; then echo "secrets/jwt-private.pem đã có, giữ nguyên"; exit 0; fi
	openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out secrets/jwt-private.pem
	openssl rsa -pubout -in secrets/jwt-private.pem -out secrets/jwt-public.pem
	chmod 600 secrets/jwt-private.pem

# --- RecSys offline bench: regression tự động so với baseline_v1 (docs/spec/bench/recsys-offline-eval.md §1, §3.1) ---
# Cần Postgres local đã seed và biến môi trường của harness: DATABASE_URL, EVAL_DATABASE_URL (.env.example) và WEAVIATE_URL
# (khoá cache vector numpy). `.env` gốc có thể trỏ VM / cloud, nên đặt RECSYS_ENV=<file export …> để nạp môi trường local
# trước khi chạy; Makefile không ghi DSN. Ví dụ:
#   make recsys-test
#   make recsys-regress RECSYS_SPLIT=llbo RECSYS_ENV=~/.vota-local.env      # mã 0 PASS/WARN · 1 FAIL · 2 không so được · 3 INCONCLUSIVE
#   make recsys-baseline RECSYS_SPLIT=temporal NOTE="lý do; history/<entry>.md" [FORCE=1]
RECSYS_PYTHON ?= $(shell if [ -x .venv/bin/python ]; then echo .venv/bin/python; elif [ -x .venv/Scripts/python.exe ]; then echo .venv/Scripts/python.exe; else echo $(PYTHON); fi)
RECSYS_ASOF ?= 20260924
RECSYS_SPLIT ?= llbo
RECSYS_VECTORS ?= numpy
RECSYS_BASELINE ?= auto
RECSYS_ENV ?=
# gán một lần (:=) để recsys-gate-run và regress dùng cùng run id
ifeq ($(origin RECSYS_RUN), undefined)
RECSYS_RUN := $(shell date +%Y%m%d-%H%M%S)-$(RECSYS_SPLIT)-regress
endif
RECSYS = PYTHONUTF8=1 $(RECSYS_PYTHON) -m src.evaluation.recsys_bench
# nạp env và chạy lệnh trên cùng một dòng logic: make cũ (không .ONESHELL) chạy mỗi dòng recipe trong một shell riêng
RECSYS_LOAD_ENV = if [ -n "$(RECSYS_ENV)" ]; then set -a; . "$(RECSYS_ENV)"; set +a; fi;
ifneq ($(filter recsys-baseline,$(MAKECMDGOALS)),)
ifeq ($(strip $(NOTE)),)
$(error recsys-baseline cần NOTE="…" (vì sao ghi baseline; trỏ entry history))
endif
endif

recsys-test:
	PYTHONUTF8=1 $(RECSYS_PYTHON) -m pytest -q src/evaluation/recsys_bench/tests

# Run gate (pool engine, numpy): engine / engine_nommr / mpd + content_profile, star_blend_a1 — đúng bộ arm của baseline_v1.
recsys-gate-run:
	$(RECSYS_LOAD_ENV) $(RECSYS) run --arm engine --arm engine_nommr --arm most_popular_in_destination \
		--algos src/evaluation/recsys_bench/algos_v1.yaml --only content_profile --only star_blend_a1 --funnel-pool engine --mode funnel \
		--split $(RECSYS_SPLIT) --vectors $(RECSYS_VECTORS) \
		--split-file src/evaluation/recsys_bench/frozen/split-$(RECSYS_SPLIT)-asof$(RECSYS_ASOF).json --run-id $(RECSYS_RUN)

# regress chỉ đọc bench_out/ và frozen/: không cần DB
recsys-regress: recsys-gate-run
	$(RECSYS) regress --run-id $(RECSYS_RUN) --baseline $(RECSYS_BASELINE)

# Ghi lại baseline chỉ khi engine đổi đã chốt / modelVersion đổi / split mới (chính sách: spec §3.1); kèm entry history + report.
recsys-baseline: recsys-gate-run
	$(RECSYS_LOAD_ENV) $(RECSYS) analyze --run-id $(RECSYS_RUN)
	$(RECSYS) baseline --run-id $(RECSYS_RUN) --note "$(NOTE)" $(if $(FORCE),--force,)
