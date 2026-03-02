.PHONY: help install build deploy clean update-cdk

# Default target
help:
	@echo "AWS GenAI Serverless Orchestration Chatbot with MLflow - Deployment Commands"
	@echo ""
	@echo "Available commands:"
	@echo "  install          - Install all dependencies (Python + Node.js + Lambda layers)"
	@echo "  build            - Build the frontend application"
	@echo "  update-cdk       - Update CDK CLI to latest version"
	@echo "  deploy           - Deploy complete infrastructure (backend + frontend)"
	@echo "  clean            - Remove all AWS resources and clean local build artifacts"
	@echo ""
	@echo "Deployment workflow:"
	@echo "  1. make install  - First time setup"
	@echo "  2. make deploy   - Deploy to AWS"
	@echo "  3. make clean    - Remove everything when done"
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

# Clean AWS resources and local files
clean:
	@echo "🧹 Cleaning AWS resources and local artifacts..."
	@./scripts/cleanup.sh