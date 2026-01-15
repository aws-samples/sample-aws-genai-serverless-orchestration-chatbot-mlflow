# stacks/sagemaker_base_stack.py
from aws_cdk import Aspects, CfnOutput, NestedStack, RemovalPolicy, Tags
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as logs
from cdk_nag import AwsSolutionsChecks, NagSuppressions
from constructs import Construct


class SageMakerBaseStack(NestedStack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        vpc,
        kms_key_arn: str,
        sagemaker_role_name: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # SageMaker execution role with explicit name and permissions
        self.sagemaker_role = iam.Role(
            self,
            "SageMakerExecutionRole",
            role_name=sagemaker_role_name,
            assumed_by=iam.ServicePrincipal("sagemaker.amazonaws.com"),
        )

        # Add SageMaker permissions
        self.sagemaker_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "sagemaker:CreateExperiment",
                    "sagemaker:DescribeExperiment",
                    "sagemaker:ListExperiments",
                    "sagemaker:UpdateExperiment",
                    "sagemaker:DeleteExperiment",
                    "sagemaker:CreateTrial",
                    "sagemaker:DescribeTrial",
                    "sagemaker:ListTrials",
                    "sagemaker:UpdateTrial",
                    "sagemaker:DeleteTrial",
                    "sagemaker:CreateTrialComponent",
                    "sagemaker:DescribeTrialComponent",
                    "sagemaker:ListTrialComponents",
                    "sagemaker:UpdateTrialComponent",
                    "sagemaker:DeleteTrialComponent",
                    "sagemaker:CreateMLflowTrackingServer",
                    "sagemaker:DescribeMLflowTrackingServer",
                    "sagemaker:UpdateMLflowTrackingServer",
                    "sagemaker:DeleteMLflowTrackingServer",
                    "sagemaker:ListMLflowTrackingServers",
                    "sagemaker:CreatePresignedMLflowTrackingServerUrl",
                    "sagemaker:ListSpaces",
                    "sagemaker:ListApps",
                    "sagemaker:DescribeApp",
                    "sagemaker:DescribeDomain",
                    "sagemaker:ListDomains",
                    "sagemaker:DescribeUserProfile",
                    "sagemaker:ListUserProfiles",
                    "sagemaker:CreatePresignedDomainUrl",
                ],
                resources=[
                    f"arn:aws:sagemaker:{self.region}:{self.account}:experiment/*",
                    f"arn:aws:sagemaker:{self.region}:{self.account}:trial/*",
                    f"arn:aws:sagemaker:{self.region}:{self.account}:trial-component/*",
                    f"arn:aws:sagemaker:{self.region}:{self.account}:mlflow-tracking-server/*",
                    f"arn:aws:sagemaker:{self.region}:{self.account}:domain/*",
                    f"arn:aws:sagemaker:{self.region}:{self.account}:user-profile/*",
                    f"arn:aws:sagemaker:{self.region}:{self.account}:space/*",
                    f"arn:aws:sagemaker:{self.region}:{self.account}:app/*",
                ],
            )
        )

        # Add S3 permissions for the conversation table and MLflow artifacts
        self.sagemaker_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                    "s3:ListBucket",
                    "s3:GetBucketLocation",
                ],
                resources=["arn:aws:s3:::*mlflow*", "arn:aws:s3:::*mlflow*/*"],
            )
        )

        # Add DynamoDB permissions for conversation table
        self.sagemaker_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:DeleteItem",
                    "dynamodb:Query",
                    "dynamodb:Scan",
                    "dynamodb:DescribeTable",
                ],
                resources=[
                    f"arn:aws:dynamodb:{self.region}:{self.account}:table/ConversationTable*"
                ],
            )
        )

        # Add RDS Data API permissions
        self.sagemaker_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "rds-data:ExecuteStatement",
                    "rds-data:BatchExecuteStatement",
                    "rds-data:BeginTransaction",
                    "rds-data:CommitTransaction",
                    "rds-data:RollbackTransaction",
                ],
                resources=[
                    f"arn:aws:rds:{self.region}:{self.account}:cluster:*chatbot*"
                ],
            )
        )

        # Add Secrets Manager permissions
        self.sagemaker_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "secretsmanager:GetSecretValue",
                    "secretsmanager:DescribeSecret",
                ],
                resources=[
                    f"arn:aws:secretsmanager:{self.region}:{self.account}:secret:*chatbot*"
                ],
            )
        )

        # Add CloudWatch Logs permissions
        self.sagemaker_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "logs:DescribeLogGroups",
                    "logs:DescribeLogStreams",
                ],
                resources=[
                    f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/sagemaker/*"
                ],
            )
        )

        # Add Bedrock permissions
        self.sagemaker_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:Converse",
                    "bedrock:ListFoundationModels",
                    "bedrock:GetFoundationModel",
                ],
                resources=[f"arn:aws:bedrock:{self.region}::foundation-model/*"],
            )
        )

        # KMS for encryption/decryption
        self.sagemaker_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "kms:Decrypt",
                    "kms:GenerateDataKey",
                    "kms:GenerateDataKeyWithoutPlaintext",
                    "kms:ReEncryptFrom",
                    "kms:ReEncryptTo",
                    "kms:DescribeKey",
                ],
                resources=[kms_key_arn],
            )
        )

        # MLflow permissions including UI access
        self.sagemaker_role.add_to_policy(
            iam.PolicyStatement(
                sid="MLflowUIAccess",
                effect=iam.Effect.ALLOW,
                actions=[
                    "sagemaker-mlflow:AccessUI",
                    "sagemaker-mlflow:CreateExperiment",
                    "sagemaker-mlflow:SearchExperiments",
                    "sagemaker-mlflow:GetExperiment",
                    "sagemaker-mlflow:ListExperiments",
                    "sagemaker-mlflow:UpdateExperiment",
                    "sagemaker-mlflow:DeleteExperiment",
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
                    "sagemaker-mlflow:CreateTrace",
                    "sagemaker-mlflow:GetTrace",
                    "sagemaker-mlflow:SearchTraces",
                    "sagemaker-mlflow:ListTraces",
                    "sagemaker-mlflow:UpdateTrace",
                    "sagemaker-mlflow:DeleteTrace",
                    "sagemaker-mlflow:LogTrace",
                    "sagemaker-mlflow:GetTraceArtifact",
                ],
                resources=[
                    f"arn:aws:sagemaker:{self.region}:{self.account}:mlflow-tracking-server/*"
                ],
            )
        )

        # Security group for SageMaker domain
        self.sagemaker_sg = ec2.SecurityGroup(
            self,
            "SageMakerSecurityGroup",
            vpc=vpc,
            description="Security group for SageMaker domain",
            allow_all_outbound=True,
        )

        # Log groups with retention policies
        self.studio_logs = logs.LogGroup(
            self,
            "SageMakerStudioLogs",
            log_group_name="/aws/sagemaker/studio-" + self.stack_name,
            removal_policy=RemovalPolicy.DESTROY,
            retention=logs.RetentionDays.ONE_WEEK,
        )

        self.domain_logs = logs.LogGroup(
            self,
            "SageMakerDomainLogs",
            log_group_name="/aws/sagemaker/domain-" + self.stack_name,
            removal_policy=RemovalPolicy.DESTROY,
            retention=logs.RetentionDays.ONE_WEEK,
        )

        self.lifecycle_logs = logs.LogGroup(
            self,
            "SageMakerLifecycleConfigLogs",
            log_group_name="/aws/sagemaker/studio-lifecycle-config-" + self.stack_name,
            removal_policy=RemovalPolicy.DESTROY,
            retention=logs.RetentionDays.ONE_WEEK,
        )

        # Output the role ARN for reference
        CfnOutput(
            self,
            "SageMakerExecutionRoleArn",
            value=self.sagemaker_role.role_arn,
            description="SageMaker Execution Role ARN with MLflow permissions",
        )

        # Apply tags to all resources in this stack
        Tags.of(self).add("Project", "BedrockChatbot")
        Tags.of(self).add("Environment", "Demo")
        Tags.of(self).add("ManagedBy", "CDK")
        Tags.of(self).add("Application", "GenAI-MLflow-Orchestration")
        Tags.of(self).add("Component", "SageMaker")

        # Apply all CDK Nag suppressions at the stack level
        Aspects.of(self).add(AwsSolutionsChecks())

        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Wildcard permissions required for: S3 MLflow artifacts, CloudWatch log streams, Bedrock foundation models, and resource pattern matching.",
                }
            ],
        )
