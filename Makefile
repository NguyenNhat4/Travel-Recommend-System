SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c
.ONESHELL:

PYTHON ?= python
AS_OF ?= $(shell date +%F)
SEED ?= 42
CATALOG_SNAPSHOT ?= data_collection/snapshots/2026-09-21/products.jsonl.gz
LOCAL_SEED_DATABASE_URL = postgresql://postgres:postgres@localhost:5432/vota
LOCAL_INSIDER_DATABASE_URL = postgresql://postgres:postgres@localhost:5432/insider

.PHONY: chat chat-full chat-api chat-ui chat-logs test-llm demo-db demo-db-reset verify-db backend

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
	export ITINERARY_DATA_MODE="$${ITINERARY_DATA_MODE:-fixture}"
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
	sleep 1
	if ! kill -0 "$${BACKEND_PID}" 2>/dev/null; then
		echo "FastAPI đã dừng khi khởi động."
		exit 1
	fi
	echo "Mở UI tại http://127.0.0.1:$${STREAMLIT_PORT}"
	echo "Nhấn Ctrl+C để dừng cả hai process."
	"$${PYTHON_BIN}" -m streamlit run src/evaluation/agent/streamlit_app.py \
		--server.port "$${STREAMLIT_PORT}" \
		> >(tee -a "$${LOG_FILE}") 2>&1

# Giữ alias cũ để không làm hỏng lệnh đang dùng.
chat-full: chat

# Chỉ chạy Backend FastAPI với tool fixture.
chat-api:
	@echo "Đang khởi động Backend API..."
	ITINERARY_DATA_MODE=$${ITINERARY_DATA_MODE:-fixture} \
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
