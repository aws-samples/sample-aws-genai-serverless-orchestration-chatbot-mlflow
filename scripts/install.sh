#!/bin/bash
set -e

# Get the project root directory (one level up from scripts)
PROJECT_ROOT=$(pwd)

echo "🔧 Installing AWS GenAI Serverless Orchestration Chatbot with MLflow dependencies..."

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
  echo "❌ Python 3 is required but not installed."
  exit 1
fi

# Create and activate Python virtual environment at project root
echo "📦 Setting up Python virtual environment..."
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate

# Install Python dependencies for backend and infrastructure
echo "📦 Installing Python dependencies..."
pip install --upgrade pip

# Install Node.js v22.17.1 using nvm
echo "📦 Installing Node.js v22.17.1 using nvm..."

# Check if nvm is already installed
if [ ! -s "$HOME/.nvm/nvm.sh" ]; then
  echo "📦 Installing nvm (Node Version Manager)..."
  echo "ℹ️  nvm provides consistent Node.js version management across platforms"
  
  # Download the nvm install script
  NVM_INSTALL_SCRIPT="/tmp/nvm-install.sh"
  # Version pinning: Update both NVM_VERSION and EXPECTED_CHECKSUM together
  # To update: 
  #   1. Visit https://github.com/nvm-sh/nvm/releases
  #   2. Choose the desired version
  #   3. Download install.sh and calculate: sha256sum install.sh
  #   4. Update both variables below
  NVM_VERSION="v0.40.3"
  EXPECTED_CHECKSUM="2d8359a64a3cb07c02389ad88ceecd43f2fa469c06104f92f98df5b6f315275f"
  
  echo "📥 Downloading nvm install script from official repository..."
  if ! curl -fsSL -o "$NVM_INSTALL_SCRIPT" "https://raw.githubusercontent.com/nvm-sh/nvm/$NVM_VERSION/install.sh"; then
    echo "❌ Failed to download nvm install script"
    exit 1
  fi
  
  # Verify checksum for security
  echo "🔐 Verifying script integrity (version: $NVM_VERSION)..."
  ACTUAL_CHECKSUM=$(sha256sum "$NVM_INSTALL_SCRIPT" | cut -d' ' -f1)
  if [ "$ACTUAL_CHECKSUM" != "$EXPECTED_CHECKSUM" ]; then
    echo "❌ Checksum verification failed - potential security risk"
    echo "   Expected: $EXPECTED_CHECKSUM"
    echo "   Actual:   $ACTUAL_CHECKSUM"
    echo ""
    echo "   This could mean:"
    echo "   1. The file was tampered with (security risk)"
    echo "   2. NVM version $NVM_VERSION was updated (update checksum)"
    echo ""
    echo "   To update the checksum:"
    echo "   1. Verify the version at: https://github.com/nvm-sh/nvm/releases/tag/$NVM_VERSION"
    echo "   2. Calculate checksum: curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/$NVM_VERSION/install.sh | sha256sum"
    echo "   3. Update EXPECTED_CHECKSUM in this script"
    rm -f "$NVM_INSTALL_SCRIPT"
    exit 1
  fi
  
  echo "✅ Checksum verified successfully"
  
  # Execute the downloaded script
  bash "$NVM_INSTALL_SCRIPT"
  
  # Clean up
  rm -f "$NVM_INSTALL_SCRIPT"
fi

# Load nvm (in lieu of restarting the shell)
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"

# Download and install Node.js v22.17.1
echo "📦 Installing Node.js v22.17.1..."
nvm install 22.17.1
nvm use 22.17.1

# Verify the Node.js version
if ! command -v node &> /dev/null; then
  echo "❌ Node.js installation failed."
  exit 1
fi

echo "✅ Node.js $(node -v) installed successfully"
echo "✅ npm $(npm -v) available"
echo "✅ Current Node.js version: $(nvm current)"

# Backend dependencies
echo "📦 Installing backend dependencies..."
cd "$PROJECT_ROOT/backend"
pip install -r requirements.txt

# Infrastructure dependencies
echo "📦 Installing infrastructure dependencies..."
cd "$PROJECT_ROOT/infra"
pip install -r requirements.txt

# Build Lambda layer for database initializer
echo "📦 Building Lambda layer for database initializer..."
cd "$PROJECT_ROOT/infra/initializerLambda"
chmod +x build_layer.sh
./build_layer.sh

# Install Node.js dependencies for frontend
echo "📦 Installing Node.js dependencies for frontend..."
cd "$PROJECT_ROOT/frontend"
npm install

# Build frontend
echo "📦 Building frontend..."
npm run build

# Return to project root
cd "$PROJECT_ROOT"

# Check if AWS CLI is available
if ! command -v aws &> /dev/null; then
    echo "⚠️  AWS CLI is not installed. Please install it for deployment."
    echo "   Visit: https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
fi

# Check if CDK CLI is available
if ! command -v cdk &> /dev/null; then
    echo "⚠️  AWS CDK CLI is not installed. Installing globally..."
    npm install -g aws-cdk
fi

# Check if Docker is available and install buildx if needed
if command -v docker &> /dev/null; then
    echo "📦 Checking Docker buildx..."
    if ! docker buildx version &> /dev/null; then
        echo "📦 Installing Docker buildx..."
        # On macOS, buildx should be available with Docker Desktop
        # If not, we'll create a builder instance
        docker buildx create --name mybuilder --use --bootstrap 2>/dev/null || true
        echo "✅ Docker buildx configured"
    else
        echo "✅ Docker buildx already available"
    fi
else
    echo "⚠️  Docker is not installed. Please install Docker Desktop for deployment."
    echo "   Visit: https://docs.docker.com/desktop/install/mac-install/"
fi

echo "✅ Dependencies installed successfully!"
echo ""
echo "Next steps:"
echo "  1. Configure AWS credentials: aws configure"
echo "  2. Bootstrap CDK (if first time): make deploy-infra"
echo "  3. Deploy the application: make deploy"
