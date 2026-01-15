"""
MLflow tracking server infrastructure stack.

This module creates a SageMaker MLflow tracking server with S3 artifact storage,
IAM roles, security groups, and resource policies for experiment tracking.
"""

from aws_cdk import Aspects, CfnOutput, NestedStack, RemovalPolicy, Tags
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sagemaker as sagemaker
from cdk_nag import AwsSolutionsChecks, NagSuppressions
from constructs import Construct


class MLflowStack(NestedStack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc,
        mlflow_server_name: str,
        mlflow_version: str,
        mlflow_security_group_name: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.vpc = vpc

        # S3 bucket for access logs
        access_logs_bucket = s3.Bucket(
            self,
            "MLflowAccessLogsBucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
        )

        # S3 bucket for MLflow artifacts with security best practices
        self.mlflow_bucket = s3.Bucket(
            self,
            "MLflowArtifactBucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            versioned=True,
            server_access_logs_bucket=access_logs_bucket,
            server_access_logs_prefix="mlflow-access-logs/",
        )

        # Security group
        self.mlflow_security_group = ec2.SecurityGroup(
            self,
            "MLflowSecurityGroup",
            vpc=vpc,
            description="Security group for MLflow tracking server",
            allow_all_outbound=False,
            security_group_name=mlflow_security_group_name,
        )

        self.mlflow_security_group.add_egress_rule(
            ec2.Peer.ipv4(vpc.vpc_cidr_block),
            ec2.Port.tcp(443),
            "Allow HTTPS outbound within VPC",
        )

        # IAM role
        mlflow_role = iam.Role(
            self,
            "MLflowRole",
            assumed_by=iam.ServicePrincipal("sagemaker.amazonaws.com"),
            description="Role for MLflow tracking server",
        )

        # SageMaker permissions
        mlflow_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "sagemaker:CreateMLflowTrackingServer",
                    "sagemaker:DescribeMLflowTrackingServer",
                    "sagemaker:UpdateMLflowTrackingServer",
                    "sagemaker:DeleteMLflowTrackingServer",
                    "sagemaker:ListMLflowTrackingServers",
                    "sagemaker:CreatePresignedMLflowTrackingServerUrl",
                ],
                resources=[
                    f"arn:aws:sagemaker:{self.region}:{self.account}:mlflow-tracking-server/*"
                ],
            )
        )

        mlflow_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                    "s3:ListBucket",
                    "s3:GetBucketLocation",
                    "s3:AbortMultipartUpload",
                    "s3:ListMultipartUploadParts",
                ],
                resources=[
                    self.mlflow_bucket.bucket_arn,
                    f"{self.mlflow_bucket.bucket_arn}/*",
                ],
            )
        )

        mlflow_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "logs:DescribeLogGroups",
                    "logs:DescribeLogStreams",
                ],
                resources=[
                    f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/sagemaker/mlflow*",
                    f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/sagemaker/mlflow*:*",
                ],
            )
        )

        # MLflow Permissions
        mlflow_role.add_to_policy(
            iam.PolicyStatement(
                sid="MLflowTrackingServerPermissions",
                effect=iam.Effect.ALLOW,
                actions=[
                    "sagemaker-mlflow:AccessUI",
                    "sagemaker-mlflow:CreateExperiment",
                    "sagemaker-mlflow:SearchExperiments",
                    "sagemaker-mlflow:GetExperiment",
                    "sagemaker-mlflow:ListExperiments",
                    "sagemaker-mlflow:CreateRun",
                    "sagemaker-mlflow:UpdateRun",
                    "sagemaker-mlflow:DeleteRun",
                    "sagemaker-mlflow:SearchRuns",
                    "sagemaker-mlflow:GetRun",
                    "sagemaker-mlflow:LogMetric",
                    "sagemaker-mlflow:LogParam",
                    "sagemaker-mlflow:LogArtifact",
                    "sagemaker-mlflow:SetTag",
                    "sagemaker-mlflow:DeleteTag",
                ],
                resources=[
                    f"arn:aws:sagemaker:{self.region}:{self.account}:mlflow-tracking-server/*"
                ],
            )
        )

        # Log group with retention policy
        self.mlflow_logs = logs.LogGroup(
            self,
            "MLflowLogs",
            log_group_name="/aws/sagemaker/mlflow",
            removal_policy=RemovalPolicy.DESTROY,
            retention=logs.RetentionDays.ONE_WEEK,
        )

        # MLflow tracking server
        self.tracking_server = sagemaker.CfnMlflowTrackingServer(
            self,
            "MLflowTrackingServer",
            role_arn=mlflow_role.role_arn,
            tracking_server_name=mlflow_server_name,
            artifact_store_uri=f"s3://{self.mlflow_bucket.bucket_name}",
            mlflow_version=mlflow_version,
            tags=[
                {"key": "Project", "value": "BedrockChatbot"},
                {"key": "Environment", "value": "Demo"},
            ],
        )

        # Grant S3 access
        self.mlflow_bucket.grant_read_write(mlflow_role)

        # Store tracking server ID for other stacks
        self.tracking_server_id = mlflow_server_name

        # Outputs
        CfnOutput(
            self,
            "MLflowTrackingServerID",
            value=self.tracking_server.ref,
            description="MLflow Tracking Server ID",
        )

        CfnOutput(
            self,
            "MLflowTrackingServerName",
            value=self.tracking_server.tracking_server_name,
            description="MLflow Tracking Server Name",
        )

        CfnOutput(
            self,
            "MLflowArtifactStoreURI",
            value=f"s3://{self.mlflow_bucket.bucket_name}",
            description="MLflow Artifact Store URI",
        )

        # Apply tags to all resources in this stack
        Tags.of(self).add("Project", "BedrockChatbot")
        Tags.of(self).add("Environment", "Demo")
        Tags.of(self).add("ManagedBy", "CDK")
        Tags.of(self).add("Application", "GenAI-MLflow-Orchestration")
        Tags.of(self).add("Component", "MLflow")

        # Apply all CDK Nag suppressions at the stack level
        Aspects.of(self).add(AwsSolutionsChecks())

        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "CDK Custom Resource Lambda requires AWSLambdaBasicExecutionRole for CloudWatch operations.",
                }
            ],
        )

        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Wildcard permissions required for: S3 object operations, CloudWatch log streams, and SageMaker MLflow resource management.",
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
