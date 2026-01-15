.PHONY: help install build deploy deploy-legacy deploy-backend deploy-frontend clean update-cdk

# Default target
help:
	@echo "AWS GenAI Serverless Orchestration Chatbot with MLflow - Deployment Commands"
	@echo ""
	@echo "Available commands:"
	@echo "  install          - Install all dependencies (Python + Node.js)"
	@echo "  build            - Build the frontend application"
	@echo "  update-cdk       - Update CDK CLI to latest version"
	@echo "  deploy           - Deploy everything (backend + frontend)"
	@echo "  clean            - Clean build artifacts"
	@echo ""

# Install dependencies
install:
	@echo "🔧 Installing dependencies..."
	@./scripts/install.sh

# Build frontend
build:
	@echo "📦 Building frontend..."
	@cd frontend && npm run build

# Update CDK CLI to latest version
update-cdk:
	@echo "📦 Updating CDK CLI to latest version..."
	@sudo npm install -g aws-cdk@latest
	@echo "✅ CDK CLI updated successfully"
	@cdk --version

# Deploy everything (using the direct method that works)
deploy:
	@echo "🚀 Deploying complete application..."
	@./scripts/deploy.sh

# Clean build artifacts
clean:
	@echo "🧹 Cleaning build artifacts..."
	@./scripts/cleanup.sh
	@rm -rf frontend/build
	@rm -rf infra/cdk.out
	@rm -rf .venv
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@find . -type d -name "*.egg-info" -exec rm -rf {} +
	@find . -type d -name ".pytest_cache" -exec rm -rf {} +
	@find . -type f -name "*.pyc" -delete