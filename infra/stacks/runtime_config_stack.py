"""
Runtime configuration stack for React app.

This stack creates a Lambda-backed custom resource that generates
the config.json file with the actual WebSocket API URL for the React app.
"""

import os

from aws_cdk import Aspects, CustomResource, Duration, NestedStack, Tags
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_s3 as s3
from cdk_nag import AwsSolutionsChecks, NagSuppressions
from constructs import Construct


class RuntimeConfigStack(NestedStack):
    """
    Stack that generates runtime configuration for the React application.

    This stack creates a Lambda function that generates config.json with the
    actual WebSocket API URL and uploads it to the S3 bucket.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        website_bucket: s3.Bucket,
        api_url: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Get path to Lambda function code
        lambda_code_path = os.path.join(
            os.path.dirname(__file__), "../lambda_functions/config_generator.py"
        )

        # Create custom IAM role for config generator Lambda
        config_lambda_role = iam.Role(
            self,
            "ConfigGeneratorLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Role for config generator Lambda function",
        )

        # Add CloudWatch Logs permissions
        config_lambda_role.add_to_policy(
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

        # Lambda function to generate config.json
        self.config_generator_lambda = lambda_.Function(
            self,
            "ConfigGeneratorFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="config_generator.handler",
            code=lambda_.Code.from_asset(
                os.path.dirname(lambda_code_path), exclude=["*.pyc", "__pycache__"]
            ),
            role=config_lambda_role,
            timeout=Duration.minutes(2),
            description="Generates config.json for React app with WebSocket API URL",
            environment={
                "BUCKET_NAME": website_bucket.bucket_name,
                "API_URL": api_url,
                "REGION": self.region or "us-east-1",
            },
        )

        # Grant Lambda permissions to write to S3 bucket
        website_bucket.grant_write(self.config_generator_lambda)

        # Custom resource to trigger config generation
        self.config_resource = CustomResource(
            self,
            "ConfigGeneratorResource",
            service_token=self.config_generator_lambda.function_arn,
            properties={
                "BucketName": website_bucket.bucket_name,
                "ApiUrl": api_url,
                "Region": self.region or "us-east-1",
                # Force updates when API URL changes
                "ConfigHash": str(hash(api_url)),
            },
        )

        # Ensure proper cleanup on stack deletion
        self.config_resource.node.add_metadata("DeletionPolicy", "Delete")

        # Apply tags to all resources in this stack
        Tags.of(self).add("Project", "BedrockChatbot")
        Tags.of(self).add("Environment", "Demo")
        Tags.of(self).add("ManagedBy", "CDK")
        Tags.of(self).add("Application", "GenAI-MLflow-Orchestration")
        Tags.of(self).add("Component", "RuntimeConfig")

        # Apply all CDK Nag suppressions at the stack level
        Aspects.of(self).add(AwsSolutionsChecks())

        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "CloudWatch Logs operations require wildcard permissions for Lambda log stream management.",
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
