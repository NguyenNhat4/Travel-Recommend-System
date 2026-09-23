SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.ONESHELL:

PYTHON ?= python
AS_OF ?= $(shell date +%F)
SEED ?= 42
CATALOG_SNAPSHOT ?= data_collection/snapshots/2026-09-23/products.jsonl.gz
# Cổng host của Postgres; đổi khi máy đã có Postgres khác giữ 5432.
# Phải khớp POSTGRES_HOST_PORT dùng cho `docker compose up`.
POSTGRES_HOST_PORT ?= 5432
export POSTGRES_HOST_PORT
LOCAL_SEED_DATABASE_URL = postgresql://postgres:postgres@localhost:$(POSTGRES_HOST_PORT)/vota
# Runner migration cần psycopg; venv của backend có sẵn, nếu chưa tạo thì rơi về $(PYTHON).
MIGRATE_PYTHON = $(shell test -x src/backend/.venv/bin/python && echo src/backend/.venv/bin/python || echo $(PYTHON))
LOCAL_INSIDER_DATABASE_URL = postgresql://postgres:postgres@localhost:$(POSTGRES_HOST_PORT)/insider

.PHONY: chat chat-full chat-api chat-ui chat-logs web web-ui web-logs test-llm demo-db demo-db-reset verify-db index-vectors db-migrate db-migrate-status backend backend-build backend-logs backend-stop backend-local

# Chạy trọn bộ FastAPI + Streamlit; Ctrl+C sẽ dừng cả hai.
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
	export ITINERARY_DATA_MODE="$${ITINERARY_DATA_MODE:-http}"
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

# Giữ alias cũ để không làm hỏng lệnh đang dùng.
chat-full: chat

# Chạy web chính (Next :3000 + BFF :3001) cùng FastAPI :8000; Ctrl+C dừng cả hai.
# Lưu ý: chat trong web hiện gọi /api/assistant/chat của BFF (Gemini), CHƯA gọi
# /api/v1/assistant/itineraries của FastAPI. FastAPI ở đây phục vụ các API khác
# và để sẵn cho lúc Web nối vào agent.
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
	export ITINERARY_DATA_MODE="$${ITINERARY_DATA_MODE:-http}"
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

# Chỉ chạy web chính; cần chat-api hoặc backend đang chạy ở terminal khác nếu muốn gọi FastAPI.
web-ui:
	@echo "Đang khởi động Next + BFF..."
	npm --prefix src/frontend run dev

# Theo dõi log của phiên web gần nhất.
web-logs:
	@LOG_FILE="$${WEB_DEMO_LOG_FILE:-$$(pwd)/.logs/web-demo.log}"
	if [[ ! -f "$${LOG_FILE}" ]]; then
		echo "Chưa có log. Hãy chạy make web trước."
		exit 1
	fi
	tail -n 200 -f "$${LOG_FILE}"

# Chỉ chạy Backend FastAPI; mặc định Agent gọi Search/Recommendation qua HTTP local.
chat-api:
	@echo "Đang khởi động Backend API..."
	ITINERARY_DATA_MODE=$${ITINERARY_DATA_MODE:-http} \
	ITINERARY_SERVICE_BASE_URL=$${ITINERARY_SERVICE_BASE_URL:-http://127.0.0.1:$${BACKEND_PORT:-8000}} \
		.venv/bin/uvicorn src.backend.app.main:app --reload --port $${BACKEND_PORT:-8000}

# Chỉ chạy UI; cần chat-api đang chạy ở terminal khác.
chat-ui:
	@echo "Đang khởi động Streamlit Agent Chat..."
	ASSISTANT_API_BASE_URL=$${ASSISTANT_API_BASE_URL:-http://127.0.0.1:$${BACKEND_PORT:-8000}/api/v1} \
		.venv/bin/streamlit run src/evaluation/agent/streamlit_app.py \
		--server.port $${STREAMLIT_PORT:-8502}

# Theo dõi log của phiên demo gần nhất.
chat-logs:
	@LOG_FILE="$${AGENT_DEMO_LOG_FILE:-$$(pwd)/.logs/agent-demo.log}"
	if [[ ! -f "$${LOG_FILE}" ]]; then
		echo "Chưa có log. Hãy chạy make chat trước."
		exit 1
	fi
	tail -n 200 -f "$${LOG_FILE}"

# Chạy script test kết nối LLM
test-llm:
	@echo "Đang chạy test LLM..."
	.venv/bin/python test_llm.py


demo-db:
	docker compose up -d --wait postgres
	$(MAKE) db-migrate
	cd src && SEED_DATABASE_URL=$(LOCAL_SEED_DATABASE_URL) INSIDER_DATABASE_URL=$(LOCAL_INSIDER_DATABASE_URL) $(PYTHON) -m data_collection.seed --products $(CATALOG_SNAPSHOT) --as-of $(AS_OF) --seed $(SEED)
	$(MAKE) verify-db

demo-db-reset:
	docker compose up -d --wait postgres
	$(MAKE) db-migrate
	cd src && SEED_DATABASE_URL=$(LOCAL_SEED_DATABASE_URL) INSIDER_DATABASE_URL=$(LOCAL_INSIDER_DATABASE_URL) $(PYTHON) -m data_collection.seed --products $(CATALOG_SNAPSHOT) --as-of $(AS_OF) --seed $(SEED) --reset
	$(MAKE) verify-db

verify-db:
	docker compose exec -T postgres psql -U postgres -d vota < db/verify.sql
	docker compose exec -T postgres psql -U postgres -d insider < db/verify_insider.sql

# Job tốn quota Cohere nên không tự chạy trong demo-db. Cần COHERE_API_KEY trong .env.
index-vectors:
	docker compose up -d --wait postgres weaviate
	$(PYTHON) -m src.backend.jobs.embed_products

# Áp thay đổi schema lên database ĐANG CÓ DỮ LIỆU, không xoá gì (db/migrations/README.md).
# db/init/*.sql chỉ chạy lúc initdb trên volume rỗng nên không dùng được cho máy đã seed.
db-migrate:
	docker compose up -d --wait postgres
	SEED_DATABASE_URL=$(LOCAL_SEED_DATABASE_URL) $(MIGRATE_PYTHON) db/migrations/run.py

db-migrate-status:
	SEED_DATABASE_URL=$(LOCAL_SEED_DATABASE_URL) $(MIGRATE_PYTHON) db/migrations/run.py --status

backend:
	docker compose up -d --build backend
	@echo "Backend API: http://localhost:$${BACKEND_PORT:-8000}"

backend-build:
	docker compose build backend

backend-logs:
	docker compose logs -f backend

# Chỉ dừng Backend; PostgreSQL và volume dữ liệu được giữ nguyên.
backend-stop:
	docker compose stop backend

# Chạy trực tiếp trên máy khi cần reload nhanh, không dùng container Backend.
backend-local:
	ITINERARY_DATA_MODE=$${ITINERARY_DATA_MODE:-fixture} \
		$(PYTHON) -m uvicorn src.backend.app.main:app --reload --host 127.0.0.1 --port $${BACKEND_PORT:-8000}
