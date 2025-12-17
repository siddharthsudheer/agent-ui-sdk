.PHONY: run dev install install-agent install-ui clean help

# Default target
.DEFAULT_GOAL := help

help: ## Show this help message
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

run: ## Start the agent server (backend only)
	@echo "Starting agent server..."
	@echo "Make sure esbuild is installed: npm install -g esbuild"
	cd agent && uv run python agent.py

dev: ## Start both UI and agent in development mode
	@echo "Starting development servers..."
	npm run dev

install: install-agent install-ui ## Install all dependencies (agent + UI)

install-agent: ## Install Python dependencies for the agent
	@echo "Installing agent dependencies..."
	cd agent && uv pip install -r requirements.txt
	@echo "Agent dependencies installed!"

install-ui: ## Install Node.js dependencies for the UI
	@echo "Installing UI dependencies..."
	npm install
	@echo "UI dependencies installed!"

clean: ## Clean up build artifacts and caches
	@echo "Cleaning up..."
# 	rm -rf agent/.venv
	rm -rf agent/__pycache__
	rm -rf agent/sidd_agent_ui_sdk/__pycache__
# 	rm -rf node_modules
	rm -rf .next
	rm -rf /tmp/sidd-agent-ui-cache
	@echo "Cleanup complete!"

test-bundle: ## Test UI bundling (requires esbuild)
	@echo "Testing UI bundling..."
	@which esbuild > /dev/null || (echo "Error: esbuild not found. Install with: npm install -g esbuild" && exit 1)
	@echo "esbuild found!"
	cd agent/ui && esbuild index.tsx --bundle --format=iife --jsx=automatic

.PHONY: check-esbuild
check-esbuild: ## Check if esbuild is installed
	@which esbuild > /dev/null && echo "✓ esbuild is installed" || echo "✗ esbuild not found. Install with: npm install -g esbuild"
