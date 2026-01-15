"""
PostgreSQL RDS database infrastructure stack.

This module defines the RDS PostgreSQL database configuration with security
groups, encryption, backup settings, and initialization Lambda function.
"""

import os
from datetime import datetime

import pytz
from aws_cdk import Aspects, CustomResource, Duration, NestedStack, RemovalPolicy, Tags
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_kms as kms
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_rds as rds
from aws_cdk import custom_resources as cr
from cdk_nag import AwsSolutionsChecks, NagSuppressions
from constructs import Construct


class DatabaseStack(NestedStack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc,
        database_name: str,
        database_port: str,
        database_instance_id: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create Security Groups
        self.db_security_group = ec2.SecurityGroup(
            self,
            "DatabaseSecurityGroup",
            vpc=vpc,
            description="Security group for RDS database",
            allow_all_outbound=True,
            security_group_name="bedrock-chatbot-db-sg",
        )

        self.lambda_security_group = ec2.SecurityGroup(
            self,
            "LambdaSecurityGroup",
            vpc=vpc,
            description="Security group for Lambda function",
            allow_all_outbound=True,
            security_group_name="bedrock-chatbot-lambda-sg",
        )

        # Allow Lambda to connect to RDS
        self.db_security_group.add_ingress_rule(
            peer=self.lambda_security_group,
            connection=ec2.Port.tcp(5432),
            description="Allow Lambda to connect to RDS",
        )

        # Allow connections from the entire VPC CIDR range
        self.db_security_group.add_ingress_rule(
            peer=ec2.Peer.ipv4(vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(5432),
            description="Allow connections from VPC CIDR range",
        )
        # Create KMS key for database encryption
        database_encryption_key = kms.Key(
            self,
            "DatabaseEncryptionKey",
            description="KMS key for RDS database encryption",
            enable_key_rotation=True,
            removal_policy=RemovalPolicy.DESTROY,
            alias="bedrock-chatbot-db-key",
        )
        # Create PostgreSQL database
        self.database = rds.DatabaseInstance(
            self,
            "ChatbotDatabase",
            instance_identifier=database_instance_id,
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_14
            ),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.BURSTABLE4_GRAVITON, ec2.InstanceSize.MEDIUM
            ),
            storage_encrypted=True,
            storage_encryption_key=database_encryption_key,
            security_groups=[self.db_security_group],
            port=int(database_port),
            database_name=database_name,
            multi_az=False,
            deletion_protection=False,
            backup_retention=Duration.days(1),
            removal_policy=RemovalPolicy.DESTROY,
            enable_performance_insights=True,
            cloudwatch_logs_exports=["postgresql", "upgrade"],
        )

        # Configure automatic secret rotation for the RDS-managed secret
        self.database.add_rotation_single_user(
            automatically_after=Duration.days(30),
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
        )

        # Create Lambda Layer
        lambda_path = os.path.join(os.path.dirname(__file__), "../initializerLambda")
        dependencies_layer = lambda_.LayerVersion(
            self,
            "DatabaseDependenciesLayer",
            code=lambda_.Code.from_asset(os.path.join(lambda_path, "layers/python")),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_12],
            description="Layer containing psycopg2 and other dependencies",
        )

        # Create custom IAM role for Lambda with least privilege
        lambda_role = iam.Role(
            self,
            "DatabaseInitializerLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Role for database initializer Lambda function",
        )

        # Add custom policy for CloudWatch Logs
        lambda_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=[
                    f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/lambda/bedrock-chatbot-db-initializer",
                    f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/lambda/bedrock-chatbot-db-initializer:*",
                ],
            )
        )

        # Add custom policy for VPC access
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
                resources=["*"],
            )
        )

        # Create Lambda function
        self.initializer_lambda = lambda_.Function(
            self,
            "DatabaseInitializerFunction",
            function_name="bedrock-chatbot-db-initializer",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            code=lambda_.Code.from_asset(lambda_path),
            layers=[dependencies_layer],
            role=lambda_role,
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            security_groups=[self.lambda_security_group],
            timeout=Duration.minutes(5),
            memory_size=512,
            environment={
                "DB_SECRET_ARN": self.database.secret.secret_arn,
                "DB_NAME": database_name,
                "DB_PORT": database_port,
                "RETRY_ATTEMPTS": "5",
                "RETRY_DELAY": "5",
            },
        )

        # Grant permissions
        self.database.secret.grant_read(self.initializer_lambda)
        self.database.grant_connect(self.initializer_lambda)

        # Create Custom Resource Provider
        provider = cr.Provider(
            self,
            "InitializerProvider",
            on_event_handler=self.initializer_lambda,
            log_retention=logs.RetentionDays.ONE_WEEK,
        )

        # Create Custom Resource
        CustomResource(
            self,
            "DatabaseInitializer",
            service_token=provider.service_token,
            properties={
                "SecretArn": self.database.secret.secret_arn,
                "DatabaseName": database_name,
                "DatabasePort": database_port,
                "Timestamp": datetime.now(pytz.UTC).isoformat(),
            },
        )

        # Apply tags to all resources in this stack
        Tags.of(self).add("Project", "BedrockChatbot")
        Tags.of(self).add("Environment", "Demo")
        Tags.of(self).add("ManagedBy", "CDK")
        Tags.of(self).add("Application", "GenAI-MLflow-Orchestration")
        Tags.of(self).add("Component", "Database")

        # Apply all CDK Nag suppressions at the stack level
        Aspects.of(self).add(AwsSolutionsChecks())

        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "CDK Custom Resource Provider framework and Log Retention Lambda require AWSLambdaBasicExecutionRole for CloudWatch operations.",
                }
            ],
        )

        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "VPC operations require wildcard permissions for ENI management across availability zones.",
                }
            ],
        )

        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-RDS3",
                    "reason": "This is a demo/blog application. Multi-AZ deployment is not required for demonstration purposes and would increase costs unnecessarily.",
                }
            ],
        )

        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-RDS10",
                    "reason": "This is a demo/blog application. Deletion protection is disabled to allow easy cleanup of resources after demonstration.",
                }
            ],
        )

        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-RDS11",
                    "reason": "This is a demo/blog application. Using the default PostgreSQL port (5432) is acceptable for demonstration purposes and simplifies configuration.",
                }
            ],
        )

        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-L1",
                    "reason": "Using Python 3.12 which is the latest available runtime version for Lambda.",
                }
            ],
        )

        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "CdkNagValidationFailure",
                    "reason": "EC23 rule cannot be validated when CIDR block is referenced using an intrinsic function.",
                }
            ],
        )
