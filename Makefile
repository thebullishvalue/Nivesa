.PHONY: run install dev docker backup clean help

# ─────────────────────────────────────────
# Nivesa — Makefile
# Hemrek Capital
# ─────────────────────────────────────────

PYTHON     ?= python3
PIP        ?= pip
STREAMLIT  ?= streamlit
APP        := nivesa.py
PORT       ?= 8501

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	$(PIP) install -r requirements.txt

run: ## Run the application
	$(STREAMLIT) run $(APP) --server.port=$(PORT)

dev: ## Run with auto-reload for development
	$(STREAMLIT) run $(APP) --server.port=$(PORT) --server.runOnSave=true

docker: ## Build and run with Docker Compose
	docker compose up --build -d

docker-stop: ## Stop Docker containers
	docker compose down

backup: ## Backup the database
	@chmod +x scripts/backup.sh
	@./scripts/backup.sh

clean: ## Remove cached files and logs
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -f data/logs/*.log

lint: ## Check syntax
	$(PYTHON) -c "import ast; ast.parse(open('$(APP)').read()); print('Syntax OK')"

test-db: ## Verify database connectivity
	$(PYTHON) -c "\
import sqlite3; \
conn = sqlite3.connect('data/db/portfolio.db'); \
c = conn.cursor(); \
for t in ['securities','transactions','security_metadata']: \
    c.execute(f'SELECT COUNT(*) FROM {t}'); \
    print(f'{t}: {c.fetchone()[0]} rows'); \
conn.close()"
