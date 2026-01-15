#!/usr/bin/env python3
"""
Main CDK application for Bedrock Chatbot.

This application deploys both backend and frontend stacks in a single CDK app,
with proper dependency management and cross-stack references.
"""

import aws_cdk as cdk
from aws_cdk import App
from cdk_nag import AwsSolutionsChecks
from stacks.principal_backend import PrincipalBackendStack
from stacks.principal_frontend import PrincipalFrontendStack


class AppConfig:
    """Centralized application configuration constants."""

    # DynamoDB Configuration
    WEBSOCKET_TABLE_NAME = "websocket-connections-v2"  # DynamoDB table for WebSocket connection management
    CONVERSATION_TABLE_NAME = "bedrock-chatbot-conversations"  # DynamoDB table for chat conversation history

    # Database Configuration
    DATABASE_NAME = "chatbotdb"  # PostgreSQL database name for application data
    DATABASE_PORT = "5432"  # PostgreSQL database port number
    DATABASE_INSTANCE_ID = "bedrock-chatbot-db"  # RDS instance identifier for the PostgreSQL database

    # Lambda Configuration
    LAMBDA_MEMORY_SIZE = 4096  # Memory allocation in MB for Lambda functions
    LAMBDA_TIMEOUT_MINUTES = 15  # Maximum execution time in minutes for Lambda functions

    # MLflow Configuration
    MLFLOW_SERVER_NAME = "bedrock-chatbot-mlflow"  # SageMaker MLflow tracking server name
    MLFLOW_VERSION = "2.16"  # MLflow version to deploy on the tracking server

    # Bedrock Configuration
    CHAT_MODEL_ID = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"  # Bedrock model ID for chat responses

    # IAM Configuration
    SAGEMAKER_ROLE_NAME = "bedrock-chatbot-sagemaker-role"  # IAM role name for SageMaker execution

    # Security Group Configuration
    MLFLOW_SECURITY_GROUP_NAME = "demo-mlflow-sg"  # Security group name for MLflow tracking server
    VPC_ENDPOINT_SECURITY_GROUP_NAME = "bedrock-chatbot-endpoint-sg"  # Security group name for VPC endpoints

    # SageMaker Configuration
    SAGEMAKER_DOMAIN_NAME = "bedrock-chatbot-domain"  # SageMaker Studio domain name
    SAGEMAKER_USER_PROFILE_NAME = "default-user"  # Default user profile name for SageMaker Studio


def main():
    """Main entry point for the CDK application."""
    app = App()

    # Deploy backend stack first
    backend_stack = PrincipalBackendStack(
        app, "BedrockChatbot-Backend", config=AppConfig
    )

    # Deploy frontend stack with dependency on backend
    frontend_stack = PrincipalFrontendStack(
        app,
        "BedrockChatbot-Frontend",
        lambda_arn=backend_stack.lambda_stack.lambda_function.function_arn,
    )

    # Set explicit dependency to ensure proper deployment order
    frontend_stack.add_dependency(backend_stack)

    cdk.Aspects.of(app).add(AwsSolutionsChecks(verbose=True))

    # Synthesize the CloudFormation templates
    app.synth()


if __name__ == "__main__":
    main()
