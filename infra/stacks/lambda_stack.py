"""
AWS Lambda function infrastructure stack.

This module defines the Lambda function configuration, IAM permissions,
VPC settings, and environment variables for the chatbot backend.
"""

import os

from aws_cdk import Aspects, Duration, Fn, NestedStack, RemovalPolicy, Stack, Tags
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from cdk_nag import AwsSolutionsChecks, NagSuppressions
from constructs import Construct


class LambdaStack(NestedStack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc,
        bedrock_endpoint,
        mlflow_endpoint,
        database,
        database_security_group,
        conversation_table,
        mlflow_tracking_server_id,
        mlflow_security_group,
        mlflow_bucket,
        database_name: str,
        database_port: str,
        lambda_memory_size: int,
        lambda_timeout_minutes: int,
        websocket_table_name: str,
        chat_model_id: str,
        mlflow_server_name: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Store the conversation table reference from the DynamoDB stack
        self.conversation_table = conversation_table

        # Create CloudWatch Log Group for Bedrock calls with encryption
        self.bedrock_logs = logs.LogGroup(
            self,
            "BedrockLogsGroup",
            log_group_name="/aws/lambda/bedrock-chatbot-calls",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Create security group for Lambda with restricted outbound
        self.lambda_security_group = ec2.SecurityGroup(
            self,
            "LambdaSecurityGroup",
            vpc=vpc,
            description="Security group for Lambda function",
            allow_all_outbound=False,
        )

        # Add specific outbound rules for database access
        self.lambda_security_group.add_egress_rule(
            database_security_group,
            ec2.Port.tcp(5432),
            "Allow PostgreSQL access to RDS",
        )

        # Add outbound rule for MLflow access
        self.lambda_security_group.add_egress_rule(
            mlflow_security_group,
            ec2.Port.tcp(443),
            "Allow HTTPS access to MLflow",
        )

        # Add outbound rule for AWS services within VPC
        self.lambda_security_group.add_egress_rule(
            ec2.Peer.ipv4(vpc.vpc_cidr_block),
            ec2.Port.tcp(443),
            "Allow HTTPS access to AWS services within VPC "
            "(Bedrock, SageMaker, VPC endpoints)",
        )

        # Add outbound rule for external AWS services
        self.lambda_security_group.add_egress_rule(
            ec2.Peer.any_ipv4(),
            ec2.Port.tcp(443),
            "Allow HTTPS access to external AWS services (DynamoDB, S3)",
        )

        # Add explicit outbound rule for RDS access via VPC endpoint
        self.lambda_security_group.add_egress_rule(
            ec2.Peer.ipv4(vpc.vpc_cidr_block),
            ec2.Port.tcp(5432),
            "Allow PostgreSQL access via RDS VPC endpoint",
        )

        # Construct the MLflow ARN using the account and region
        mlflow_tracking_arn = Fn.join(
            "",
            [
                "arn:aws:sagemaker:",
                Stack.of(self).region,
                ":",
                Stack.of(self).account,
                ":mlflow-tracking-server/",
                mlflow_tracking_server_id,
            ],
        )

        # Create custom IAM role for Lambda function
        lambda_role = iam.Role(
            self,
            "BedrockChatbotLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Role for Bedrock Chatbot Lambda function",
        )

        # Add CloudWatch Logs permissions
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=[
                    f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/lambda/*"
                ],
            )
        )

        # Create Lambda function for Bedrock integration
        self.lambda_function = lambda_.DockerImageFunction(
            self,
            "BedrockChatbotFunction",
            code=lambda_.DockerImageCode.from_image_asset(
                os.path.join(os.path.dirname(__file__), "../../backend"),
                cmd=["main_handler.handler"],
            ),
            architecture=lambda_.Architecture.X86_64,
            role=lambda_role,
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            security_groups=[self.lambda_security_group],
            environment={
                "CONVERSATION_TABLE": self.conversation_table.table_name,
                "DB_SECRET_ARN": database.secret.secret_arn,
                "DB_NAME": database_name,
                "DB_PORT": database_port,
                "BEDROCK_ENDPOINT_ID": bedrock_endpoint.vpc_endpoint_id,
                "MLFLOW_TRACKING_SERVER_ID": mlflow_tracking_server_id,
                "MLFLOW_TRACKING_ARN": mlflow_tracking_arn,
                "BEDROCK_LOG_GROUP": self.bedrock_logs.log_group_name,
                "RDS_SECRET_NAME": database.secret.secret_name,
                "MODELID_CHAT": chat_model_id,
                "PGSSLMODE": "require",
                "DYNAMO_TABLE": self.conversation_table.table_name,
                "APP_REGION": Stack.of(self).region,
                "CONNECTIONS_TABLE": websocket_table_name,
            },
            timeout=Duration.minutes(lambda_timeout_minutes),
            memory_size=lambda_memory_size,
        )

        # Create log group for the Lambda function with encryption
        lambda_logs = logs.LogGroup(
            self,
            "LambdaFunctionLogs",
            log_group_name=f"/aws/lambda/{self.lambda_function.function_name}",
            removal_policy=RemovalPolicy.DESTROY,
            retention=logs.RetentionDays.ONE_WEEK,
        )

        # Grant permissions to the Lambda function
        self.conversation_table.grant_read_write_data(self.lambda_function)
        database.secret.grant_read(self.lambda_function)
        self.bedrock_logs.grant_write(self.lambda_function)

        # Create IAM policy for Bedrock access through VPC endpoint
        bedrock_policy = iam.PolicyStatement(
            actions=["bedrock:InvokeModel", "bedrock:Converse"],
            resources=[
                # Support models in current region (us-west-2)
                f"arn:aws:bedrock:*::foundation-model/anthropic.claude-3-5-sonnet-*",
                f"arn:aws:bedrock:*::foundation-model/us.anthropic.claude-3-5-sonnet-*",
                f"arn:aws:bedrock:*:{Stack.of(self).account}:inference-profile/us.anthropic.claude-3-5-sonnet-*",
            ],
            effect=iam.Effect.ALLOW,
        )

        # Create IAM policy for MLflow access through VPC endpoint
        mlflow_policy = iam.PolicyStatement(
            actions=[
                "sagemaker-mlflow:*",
                "sagemaker:CreatePresignedMLflowTrackingServerUrl",
                "sagemaker:DescribeMLflowTrackingServer",
                "sagemaker:ListMLflowTrackingServers",
                "sagemaker:InvokeEndpoint",
                "sagemaker:CreateExperiment",
                "sagemaker:DescribeExperiment",
                "sagemaker:ListExperiments",
                "sagemaker:ListSpaces",
                "sagemaker:ListApps",
                "sagemaker:DescribeApp",
                "sagemaker:CreatePresignedDomainUrl",
            ],
            resources=[
                f"arn:aws:sagemaker:{Stack.of(self).region}:{Stack.of(self).account}:mlflow-tracking-server/*",
                f"arn:aws:sagemaker:{Stack.of(self).region}:{Stack.of(self).account}:domain/*",
                f"arn:aws:sagemaker:{Stack.of(self).region}:{Stack.of(self).account}:user-profile/*",
                f"arn:aws:sagemaker:{Stack.of(self).region}:{Stack.of(self).account}:app/*",
                f"arn:aws:sagemaker:{Stack.of(self).region}:{Stack.of(self).account}:space/*",
            ],
        )

        s3_policy = iam.PolicyStatement(
            actions=[
                "s3:PutObject",
                "s3:GetObject",
                "s3:ListBucket",
                "s3:GetBucketLocation",
            ],
            resources=[mlflow_bucket.bucket_arn, f"{mlflow_bucket.bucket_arn}/*"],
        )

        # Add MLflow experiment permissions
        mlflow_experiment_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "sagemaker-mlflow:GetExperimentByName",
                "sagemaker-mlflow:CreateExperiment",
                "sagemaker-mlflow:SearchExperiments",
                "sagemaker:CreateExperiment",
                "sagemaker:ListExperiments",
                "sagemaker:GetExperiment",
                "sagemaker:SearchExperiments",
                "sagemaker:BatchGetMetrics",
                "sagemaker:BatchPutMetrics",
                "sagemaker:UpdateExperiment",
                "sagemaker:DeleteExperiment",
                "sagemaker:ListTrials",
                "sagemaker:CreateTrial",
                "sagemaker:GetTrial",
                "sagemaker:UpdateTrial",
                "sagemaker:DeleteTrial",
                "sagemaker:ListTrialComponents",
                "sagemaker:CreateTrialComponent",
                "sagemaker:GetTrialComponent",
                "sagemaker:UpdateTrialComponent",
                "sagemaker:DeleteTrialComponent",
            ],
            resources=[
                f"arn:aws:sagemaker:{Stack.of(self).region}:{Stack.of(self).account}:experiment/*",
                f"arn:aws:sagemaker:{Stack.of(self).region}:{Stack.of(self).account}:trial/*",
                f"arn:aws:sagemaker:{Stack.of(self).region}:{Stack.of(self).account}:trial-component/*",
            ],
        )

        # Add SageMaker endpoint permissions
        sagemaker_endpoint_policy = iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "sagemaker:CreatePresignedDomainUrl",
                "sagemaker:CreatePresignedNotebookInstanceUrl",
            ],
            resources=[
                f"arn:aws:sagemaker:{Stack.of(self).region}:{Stack.of(self).account}:*"
            ],
        )

        # Add VPC access permissions to custom role
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "ec2:CreateNetworkInterface",
                    "ec2:DescribeNetworkInterfaces",
                    "ec2:DeleteNetworkInterface",
                    "ec2:AttachNetworkInterface",
                    "ec2:DetachNetworkInterface",
                ],
                resources=["*"],  # VPC operations require wildcard - will suppress
            )
        )

        # Add IAM policy for DynamoDB access (both conversation table and WebSocket connections table)
        dynamodb_policy = iam.PolicyStatement(
            actions=[
                "dynamodb:GetItem",
                "dynamodb:PutItem",
                "dynamodb:UpdateItem",
                "dynamodb:DeleteItem",
                "dynamodb:Query",
                "dynamodb:Scan",
                "dynamodb:BatchGetItem",
                "dynamodb:BatchWriteItem",
                "dynamodb:DescribeTable",
            ],
            resources=[
                self.conversation_table.table_arn,
                f"{self.conversation_table.table_arn}/index/*",
                f"arn:aws:dynamodb:{Stack.of(self).region}:{Stack.of(self).account}:table/{websocket_table_name}",
                f"arn:aws:dynamodb:{Stack.of(self).region}:{Stack.of(self).account}:table/{websocket_table_name}/index/*",
            ],
            effect=iam.Effect.ALLOW,
        )

        # Add IAM policy for Secrets Manager access
        secrets_manager_policy = iam.PolicyStatement(
            actions=["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"],
            resources=[
                database.secret.secret_arn,
                f"arn:aws:secretsmanager:{Stack.of(self).region}:{Stack.of(self).account}:secret:*{database_name}*",
            ],
            effect=iam.Effect.ALLOW,
        )

        # Add IAM policy for WebSocket API Gateway management
        websocket_api_policy = iam.PolicyStatement(
            actions=["execute-api:ManageConnections"],
            resources=[
                f"arn:aws:execute-api:{Stack.of(self).region}:{Stack.of(self).account}:*/*/*/*"
            ],
            effect=iam.Effect.ALLOW,
        )

        # Add policies to Lambda role
        lambda_role.add_to_policy(bedrock_policy)
        lambda_role.add_to_policy(mlflow_policy)
        lambda_role.add_to_policy(secrets_manager_policy)
        lambda_role.add_to_policy(dynamodb_policy)
        lambda_role.add_to_policy(websocket_api_policy)
        lambda_role.add_to_policy(s3_policy)
        lambda_role.add_to_policy(mlflow_experiment_policy)
        lambda_role.add_to_policy(sagemaker_endpoint_policy)

        # Apply tags to all resources in this stack
        Tags.of(self).add("Project", "BedrockChatbot")
        Tags.of(self).add("Environment", "Demo")
        Tags.of(self).add("ManagedBy", "CDK")
        Tags.of(self).add("Application", "GenAI-MLflow-Orchestration")
        Tags.of(self).add("Component", "Lambda")

        # Apply all CDK Nag suppressions at the stack level
        Aspects.of(self).add(AwsSolutionsChecks())

        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "Lambda function may use AWS managed policies for "
                    "basic execution and VPC access.",
                }
            ],
        )

        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Wildcard permissions required for: VPC ENI management, CloudWatch log streams, DynamoDB indexes, and API Gateway WebSocket connections.",
                }
            ],
        )

        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-L1",
                    "reason": "Main Lambda function uses Docker container image which manages "
                    "runtime versions independently of Lambda runtime settings.",
                }
            ],
        )
