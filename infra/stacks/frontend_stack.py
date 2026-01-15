"""
Frontend S3 and CloudFront infrastructure stack.

This module defines the S3 bucket for website hosting, CloudFront distribution
for content delivery, and React application build and deployment process.
"""

from typing import Optional

from aws_cdk import Aspects, NestedStack, RemovalPolicy, Tags
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3deploy
from cdk_nag import AwsSolutionsChecks, NagSuppressions
from constructs import Construct


class FrontendStack(NestedStack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        lambda_arn: Optional[str] = None,
        api=None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Store API reference (not used during build, only for outputs)
        self.api = api

        # Create S3 bucket for access logs
        access_logs_bucket = s3.Bucket(
            self,
            "ChatbotWebsiteAccessLogsBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
        )

        # Create S3 bucket for website hosting
        self.website_bucket = s3.Bucket(
            self,
            "ChatbotWebsiteBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            server_access_logs_bucket=access_logs_bucket,
            server_access_logs_prefix="access-logs/",
        )

        # Add bucket policy to enforce SSL/TLS
        self.website_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                sid="DenyInsecureConnections",
                effect=iam.Effect.DENY,
                principals=[iam.AnyPrincipal()],
                actions=["s3:*"],
                resources=[
                    self.website_bucket.bucket_arn,
                    f"{self.website_bucket.bucket_arn}/*",
                ],
                conditions={"Bool": {"aws:SecureTransport": "false"}},
            )
        )

        # Add SSL policy to access logs bucket as well
        access_logs_bucket.add_to_resource_policy(
            iam.PolicyStatement(
                sid="DenyInsecureConnections",
                effect=iam.Effect.DENY,
                principals=[iam.AnyPrincipal()],
                actions=["s3:*"],
                resources=[
                    access_logs_bucket.bucket_arn,
                    f"{access_logs_bucket.bucket_arn}/*",
                ],
                conditions={"Bool": {"aws:SecureTransport": "false"}},
            )
        )

        # CloudFront OAI
        origin_access_identity = cloudfront.OriginAccessIdentity(
            self, "ChatbotOAI", comment="OAI for chatbot website"
        )

        # Grant OAI read access to bucket
        self.website_bucket.grant_read(origin_access_identity)

        # Create CloudFront distribution with security and logging
        self.distribution = cloudfront.Distribution(
            self,
            "ChatbotDistribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_identity(
                    bucket=self.website_bucket,
                    origin_access_identity=origin_access_identity,
                ),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
            ),
            default_root_object="index.html",
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                )
            ],
        )

        # Deploy to S3
        s3deploy.BucketDeployment(
            self,
            "DeployWebsite",
            sources=[s3deploy.Source.asset("../frontend/build")],
            destination_bucket=self.website_bucket,
            distribution=self.distribution,
            distribution_paths=["/*"],
        )

        # Apply tags to all resources in this stack
        Tags.of(self).add("Project", "BedrockChatbot")
        Tags.of(self).add("Environment", "Demo")
        Tags.of(self).add("ManagedBy", "CDK")
        Tags.of(self).add("Application", "GenAI-MLflow-Orchestration")
        Tags.of(self).add("Component", "Frontend")


        # Apply all CDK Nag suppressions at the stack level
        Aspects.of(self).add(AwsSolutionsChecks())

        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "CDK Bucket Deployment Lambda requires "
                    "AWSLambdaBasicExecutionRole for CloudWatch operations.",
                }
            ],
        )

        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "CDK Bucket Deployment Lambda requires wildcard "
                    "S3 permissions for deployment operations.",
                }
            ],
        )

        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-L1",
                    "reason": "CDK BucketDeployment construct manages Lambda "
                    "runtime versions automatically and uses the latest "
                    "available runtime.",
                }
            ],
        )

        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-CFR1",
                    "reason": "This is a demo/blog application. Geo restrictions "
                    "are not required for demonstration purposes and would "
                    "limit global accessibility.",
                }
            ],
        )

        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-CFR2",
                    "reason": "This is a demo/blog application. AWS WAF "
                    "integration is not required for demonstration purposes "
                    "and would increase costs unnecessarily.",
                }
            ],
        )

        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-CFR3",
                    "reason": "CloudFront access logging is disabled to avoid S3 ACL "
                    "requirements, which is a security best practice. For production "
                    "use, consider real-time logs to CloudWatch without S3 delivery.",
                }
            ],
        )

        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-CFR4",
                    "reason": "This is a demo/blog application using the default "
                    "CloudFront certificate. For production use, a custom certificate "
                    "with TLS 1.2+ would be recommended.",
                }
            ],
        )

        NagSuppressions.add_stack_suppressions(
            self,
            [
                {
                    "id": "AwsSolutions-CFR7",
                    "reason": "This demo application uses Origin Access Identity (OAI) "
                    "for compatibility with the current CDK version. Origin Access "
                    "Control (OAC) would be preferred for production use with newer "
                    "CDK versions.",
                }
            ],
        )
