#!/bin/bash
set -e

# Get the project root directory (one level up from scripts)
PROJECT_ROOT=$(pwd)

echo "🚀 Deploying AWS GenAI Serverless Orchestration Chatbot with MLflow..."

# Check if AWS CLI is configured
if ! aws sts get-caller-identity &> /dev/null; then
  echo "❌ AWS CLI is not configured or credentials are invalid."
  echo "   Run: aws configure"
  exit 1
fi

# Authenticate with ECR Public to avoid rate limits
echo "🔐 Authenticating with AWS ECR Public..."
if command -v docker &> /dev/null; then
  aws ecr-public get-login-password --region us-east-1 | docker login --username AWS --password-stdin public.ecr.aws
  echo "✅ ECR Public authentication successful"
else
  echo "⚠️  Docker not found. Skipping ECR Public authentication."
fi

# Check for Python virtual environment
if [ ! -d ".venv" ]; then
  echo "❌ Python virtual environment not found. Run: ./scripts/install.sh"
  exit 1
fi
# Activate the virtual environment
source .venv/bin/activate
echo "📦 Using Python virtual environment..."

# Load nvm and use Node.js v22.17.1
echo "📦 Loading Node.js v22.17.1..."
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"

# Use Node.js v22.17.1 if available
if command -v nvm &> /dev/null; then
  nvm use 22.17.1
  echo "✅ Using Node.js $(node -v)"
else
  echo "⚠️  nvm not found. Please run ./scripts/install.sh first"
fi

# Navigate to infra directory
cd "$PROJECT_ROOT/infra"

# Check if CDK is bootstrapped
echo "🔍 Checking CDK bootstrap status..."
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=$(aws configure get region || echo "us-east-1")
if ! aws cloudformation describe-stacks --stack-name CDKToolkit --region "$REGION" &> /dev/null; then
  echo "🔧 CDK not bootstrapped."
  exit 1
fi

# Build Lambda layer for database initializer
echo "🔧 Building Lambda layer for database initializer..."
cd "$PROJECT_ROOT/infra/initializerLambda"
./build_layer.sh
cd "$PROJECT_ROOT/infra"

# Synthesize the CDK app to check for errors
echo "🔍 Synthesizing CDK application..."
cdk synth --app "python3 app.py" --all

# Deploy the infrastructure 
echo "🚀 Deploying the infrastructure..."
cdk deploy --app "python3 app.py" --all --require-approval never


# Get backend stack outputs
echo "📋 Getting backend deployment information..."
aws cloudformation describe-stacks \
  --stack-name BedrockChatbot-Backend \
  --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
  --output table

# Get frontend stack outputs
echo "📋 Getting frontend deployment information..."
aws cloudformation describe-stacks \
  --stack-name BedrockChatbot-Frontend \
  --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
  --output table

echo "✅ Complete infrastructure deployment completed successfully!"
echo ""
echo "🌐 You can now access your application at the WebsiteURL shown above."