# Build a serverless conversational AI agent using Claude with LangGraph and managed MLflow on Amazon SageMaker AI

This repository demonstrates how to build a serverless conversational AI agent for customer service using Amazon Bedrock's Claude models, LangGraph for orchestration, and managed MLflow on Amazon SageMaker AI for observability. The solution showcases how to combine the reasoning capabilities of Large Language Models (LLMs), stateful conversation management with LangGraph, and comprehensive experiment tracking through MLflow to create intelligent customer service agents that can handle multi-turn conversations, order management, and account inquiries.

We'll walk through deploying a complete serverless architecture using AWS CDK that includes real-time WebSocket communication, VPC-secured infrastructure with private subnets for Lambda and RDS, VPC endpoints for AWS services (Bedrock, SageMaker), DynamoDB for conversation state management, PostgreSQL RDS for structured data storage, and MLflow integration for tracking all LLM interactions, performance metrics, and conversation flows. This solution enables teams to build, deploy, monitor, and continuously improve conversational AI agents with full observability and traceability through a single, integrated platform.

## Architecture Overview

![Architecture Diagram](./images/infra3.png)

### Key Components

1. **Modern Serverless Architecture**

   - **WebSocket API Only**: Real-time bidirectional communication
   - **Container-based Lambda**: Fast, efficient deployments

2. **VPC Configuration**

   - Private subnets hosting Lambda and RDS
   - Public subnets with NAT Gateway for outbound traffic
   - VPC Endpoints:
     - Bedrock Runtime
     - Bedrock API
     - SageMaker API

3. **Compute & Services**

   - **Lambda Function** (Container-based):
     - Memory: 4096 MB
     - Timeout: 15 minutes
     - Python 3.11 runtime
     - Docker container deployment
   - **WebSocket API**: Real-time chat communication
   - **Amazon Bedrock**: Claude 3.5 Sonnet model
   - **MLflow 2.16 on SageMaker**: Experiment tracking and model monitoring

4. **Storage & State Management**

   - **DynamoDB Tables**:
     - `bedrock-chatbot-conversations`: Chat history
     - `websocket-connections-v2`: Active WebSocket connections
   - **S3 Buckets**: Frontend hosting and MLflow artifacts
   - **CloudFront**: Content delivery and caching
   - **PostgreSQL RDS**: Structured data storage

5. **Security & Best Practices**
   - IAM roles with least privilege principles
   - Security groups with minimal required access
   - VPC endpoints for secure service communication
   - Encryption at rest and in transit


## Prerequisites

- AWS CLI configured with appropriate permissions
- AWS CDK CLI installed (`npm install -g aws-cdk`)
- Python 3.12 or later
- Docker installed and running
- Node.js 20+ and npm installed
- **CloudWatch Logs role ARN configured in API Gateway account settings** (required for API Gateway logging):
  - [Create IAM role with required permissions](https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-logging.html#set-up-access-logging-permissions)
  - [Configure the role in API Gateway console](https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-logging.html#set-up-access-logging-using-console) - steps 1-3 only

## Deployment Guide

### 1. Clone the repository and set up the project root

```bash
# Clone the repository
git clone https://github.com/aws-samples/sample-aws-genai-serverless-orchestration-chatbot-mlflow.git

# Navigate to the project root
cd sample-aws-genai-serverless-orchestration-chatbot-mlflow

# Store the project root path
export PROJECT_ROOT=$(pwd)
```

### 2. Bootstrap AWS Environment (required if bootstrap is not done before)

```bash
cd "$PROJECT_ROOT/infra"
cdk bootstrap
```

### 3. Install Dependencies

```bash
# Using the Makefile (recommended)
cd "$PROJECT_ROOT"
make install

# Or manually:
# Backend dependencies
cd "$PROJECT_ROOT/backend"
pip install -r requirements.txt

# Infrastructure dependencies
cd "$PROJECT_ROOT/infra"
pip install -r requirements.txt

# Build Lambda layer for database initializer
cd "$PROJECT_ROOT/infra/initializerLambda"
chmod +x build_layer.sh
./build_layer.sh

# Frontend dependencies
cd "$PROJECT_ROOT/frontend"
npm install
```

### 4. Build and Deploy Application

```bash
# Using the Makefile (recommended)
cd "$PROJECT_ROOT"
make deploy

# Or step-by-step:
# 1. Build frontend assets (if needed)
cd "$PROJECT_ROOT"
make build

# 2. Deploy complete infrastructure
cd "$PROJECT_ROOT/infra"
cdk deploy --app "python3 app.py" --all --require-approval never
```

This command deploys both stacks in the correct order:

1. **BedrockChatbot-Backend**: Backend infrastructure (VPC, Lambda, Database, MLflow)
2. **BedrockChatbot-Frontend**: Frontend with WebSocket API and runtime configuration

CDK automatically handles stack dependencies and cross-stack references.

## Cleanup

To completely remove all resources:

```bash
# Using the Makefile (recommended)
cd "$PROJECT_ROOT"
make clean

# Or manually:
cd "$PROJECT_ROOT/scripts"
./cleanup.sh
```

This script will:

1. Ask for confirmation before proceeding
2. Empty all S3 buckets to prevent deletion failures
3. Clean up SageMaker EFS file systems
4. Run `cdk destroy --all --force` to remove both stacks
5. Clean up local build artifacts

This ensures all resources are properly removed to avoid ongoing charges.

### Environment Setup (local test)

Create a `.env` file with required configurations:

```
MODELID_CHAT=
MODELID_ROUTE=
AWS_REGION=
RDS_SECRET_NAME=
DYNAMO_TABLE=
MLFLOW_TRACKING_ARN=
CONNECTIONS_TABLE=
```

## Application Workflow

![Agentic Workflow](./images/graph.png)

### Conversation Flow

1. **Entry Intent** (`entry_intent.py`):

   - Initial message processing
   - Order information extraction

2. **Order Confirmation** (`order_confirmation.py`):

   - Order validation
   - User confirmation handling

3. **Resolution** (`resolution.py`):
   - Final processing
   - Session management

### MLflow Monitoring

![MLflow Tracing](./images/mlflow_trace.png)

- **Automatic Tracing**: All Bedrock calls tracked
- **Performance Metrics**: Response latency, token usage
- **Experiment Organization**: Session-based tracking
- **Model Monitoring**: Performance over time

### Development and Testing

**Notebooks**: The `notebooks/` directory provides:

- Basic functionality testing
- Conversation flow validation
- MLflow integration testing

**Local Testing**:

```bash
# Environment setup
export MODELID_CHAT=us.anthropic.claude-3-5-sonnet-20241022-v2:0
export AWS_REGION=us-east-1
export CONNECTIONS_TABLE=websocket-connections-v2
export RDS_SECRET_NAME="arn:aws:secretsmanager:us-east-1:xxxxxxxx:secret:ChatbotDatabaseSecretxxxxxxxx"
export DYNAMO_TABLE="bedrock-chatbot-conversations"
export MLFLOW_TRACKING_ARN="arn:aws:sagemaker:us-east-1:xxxxxxx:mlflow-tracking-server/bedrock-chatbot-mlflow"
```

## Example Conversations

### Order Lookup

```
I need help with an order
```

```
My order is 32057
```

### Cancel Order

```
I need help with an order
```

```
My order is 37129
```

```
Please cancel my order
```

### Account Lookup

```
Hello, I need some help
```

```
I don't remember my order id
```

```
My email is anacarolina_silva@example.com
```

```
What are my orders
```

### Combining Requests

```
I need to cancel an order but don't remember my order id
```

```
My phone number is 312-555-8204
```

```
Yes
```

## Contributing

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License. See the LICENSE file.